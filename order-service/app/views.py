from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderListSerializer, OrderCreateSerializer
from .publisher import publish_order_created
import requests
import os

BOOK_SERVICE_URL = os.environ.get('BOOK_SERVICE_URL', 'http://book-service:8000')
CLOTHE_SERVICE_URL = os.environ.get('CLOTHE_SERVICE_URL', 'http://clothe-service:8000')
INVENTORY_SERVICE_URL = os.environ.get('INVENTORY_SERVICE_URL', 'http://inventory-service:8000')


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class OrderListCreate(APIView):
    pagination_class = StandardResultsSetPagination

    def get(self, request, customer_id=None):
        if customer_id:
            orders = Order.objects.filter(customer_id=customer_id)
        else:
            orders = Order.objects.all()
        
        # Filters
        status_filter = request.query_params.get('status')
        if status_filter:
            orders = orders.filter(status=status_filter)
        
        payment_status = request.query_params.get('payment_status')
        if payment_status:
            orders = orders.filter(payment_status=payment_status)
        
        orders = orders.order_by('-created_at')
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(orders, request)
        if page is not None:
            serializer = OrderListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        customer_id = data['customer_id']
        items = data['items']
        shipping_address = data['shipping_address']
        shipping_name = data.get('shipping_name', '')
        shipping_phone = data.get('shipping_phone', '')
        payment_method = data.get('payment_method', 'cod')
        shipping_fee = float(data.get('shipping_fee', 0))
        discount_amount = float(data.get('discount_amount', 0))
        customer_note = data.get('customer_note', '')

        if not items:
            return Response({"error": "No items in order"}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate totals
        subtotal = sum(float(item['unit_price']) * item['quantity'] for item in items)
        total_price = subtotal - discount_amount
        grand_total = total_price + shipping_fee

        # Create order
        order = Order.objects.create(
            customer_id=customer_id,
            subtotal=subtotal,
            discount_amount=discount_amount,
            total_price=total_price,
            shipping_fee=shipping_fee,
            grand_total=grand_total,
            shipping_address=shipping_address,
            shipping_name=shipping_name,
            shipping_phone=shipping_phone,
            payment_method=payment_method,
            customer_note=customer_note,
            status='pending',
            payment_status='unpaid'
        )

        # Create order items with snapshot data
        order_items_data = []
        for item in items:
            order_item = OrderItem.objects.create(
                order=order,
                book_id=item.get('book_id'),
                product_uuid=item.get('product_uuid'),
                variant_sku=item.get('variant_sku'),
                product_name=item['product_name'],
                product_type=item.get('product_type', ''),
                product_thumbnail=item.get('product_thumbnail', ''),
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total_price=float(item['unit_price']) * item['quantity'],
                variant_name=item.get('variant_name', ''),
                variant_attributes=item.get('variant_attributes', {})
            )
            order_items_data.append({
                'book_id': item.get('book_id'),
                'product_uuid': str(item['product_uuid']) if item.get('product_uuid') else None,
                'variant_sku': item.get('variant_sku'),
                'quantity': item['quantity'],
                'price': float(item['unit_price'])
            })

        # Publish event for Saga
        publish_order_created({
            "order_id": order.id,
            "order_number": order.order_number,
            "customer_id": customer_id,
            "amount": float(grand_total),
            "payment_method": payment_method,
            "shipping_address": shipping_address,
            "items": order_items_data
        })

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetail(APIView):
    def get(self, request, pk):
        try:
            order = Order.objects.prefetch_related('items').get(pk=pk)
            serializer = OrderSerializer(order)
            return Response(serializer.data)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        """Cancel an order with compensation logic"""
        try:
            order = Order.objects.prefetch_related('items').get(pk=pk)
            
            # Only allow cancellation for certain statuses
            if order.status not in ['pending', 'confirmed', 'paid']:
                return Response({
                    "error": "Cannot cancel this order at current stage"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Compensation: Restore stock / Release reservations
            for item in order.items.all():
                try:
                    if item.variant_sku:
                        # New approach: Release inventory reservation
                        requests.post(
                            f"{INVENTORY_SERVICE_URL}/stock/release/{order.id}/",
                            json={"reason": "Order cancelled by customer"},
                            timeout=5
                        )
                    elif item.book_id:
                        # Old approach: Restore stock
                        if item.book_id > 1000000:
                            real_id = item.book_id - 1000000
                            requests.post(
                                f"{CLOTHE_SERVICE_URL}/clothes/{real_id}/restore-stock/",
                                json={"quantity": item.quantity},
                                timeout=3
                            )
                        else:
                            requests.post(
                                f"{BOOK_SERVICE_URL}/books/{item.book_id}/restore-stock/",
                                json={"quantity": item.quantity},
                                timeout=3
                            )
                except Exception as e:
                    print(f"Error restoring stock: {e}")
            
            order.status = 'cancelled'
            order.cancelled_at = timezone.now()
            order.save()
            
            return Response({
                "status": "cancelled",
                "message": "Order cancelled and stock restored."
            })
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        """Update order status"""
        try:
            order = Order.objects.get(pk=pk)
            
            # Update status
            new_status = request.data.get("status")
            if new_status:
                order.status = new_status
                # Update timestamp based on status
                if new_status == 'confirmed':
                    order.confirmed_at = timezone.now()
                elif new_status == 'shipping':
                    order.shipped_at = timezone.now()
                elif new_status == 'delivered':
                    order.delivered_at = timezone.now()
                elif new_status == 'cancelled':
                    order.cancelled_at = timezone.now()
            
            # Update payment status
            new_payment_status = request.data.get("payment_status")
            if new_payment_status:
                order.payment_status = new_payment_status
            
            # Update tracking number
            tracking = request.data.get("tracking_number")
            if tracking:
                order.tracking_number = tracking
            
            # Update admin note
            admin_note = request.data.get("admin_note")
            if admin_note:
                order.admin_note = admin_note
            
            order.save()
            return Response(OrderSerializer(order).data)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)


class OrderByNumber(APIView):
    """Get order by order_number"""
    
    def get(self, request, order_number):
        try:
            order = Order.objects.prefetch_related('items').get(order_number=order_number)
            serializer = OrderSerializer(order)
            return Response(serializer.data)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)