from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

from .models import Warehouse, ProductVariant, InventoryItem, StockMovement, StockReservation
from .serializers import (
    WarehouseSerializer, WarehouseListSerializer,
    ProductVariantSerializer, ProductVariantListSerializer,
    InventoryItemSerializer, StockMovementSerializer, StockReservationSerializer,
    StockAdjustSerializer, ReserveStockSerializer, CreateVariantSerializer, InitializeStockSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


# ==================== Warehouse Views ====================

class WarehouseListCreate(APIView):
    """List all warehouses or create a new one"""
    
    def get(self, request):
        warehouses = Warehouse.objects.all()
        
        active_only = request.query_params.get('active', 'true').lower() == 'true'
        if active_only:
            warehouses = warehouses.filter(is_active=True)
        
        serializer = WarehouseListSerializer(warehouses, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WarehouseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WarehouseDetail(APIView):
    """Retrieve, update or delete a warehouse"""
    
    def get(self, request, code):
        warehouse = get_object_or_404(Warehouse, code=code)
        serializer = WarehouseSerializer(warehouse)
        return Response(serializer.data)

    def patch(self, request, code):
        warehouse = get_object_or_404(Warehouse, code=code)
        serializer = WarehouseSerializer(warehouse, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== Variant Views ====================

class VariantListCreate(APIView):
    """List all variants or create a new one"""
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        variants = ProductVariant.objects.all()
        
        product_uuid = request.query_params.get('product_uuid')
        if product_uuid:
            variants = variants.filter(product_uuid=product_uuid)
        
        active_only = request.query_params.get('active', 'true').lower() == 'true'
        if active_only:
            variants = variants.filter(is_active=True)
        
        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(variants, request)
        if page is not None:
            serializer = ProductVariantListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = ProductVariantListSerializer(variants, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CreateVariantSerializer(data=request.data)
        if serializer.is_valid():
            variant = serializer.save()
            return Response(ProductVariantSerializer(variant).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VariantDetail(APIView):
    """Retrieve, update or delete a variant by SKU"""
    
    def get(self, request, sku):
        variant = get_object_or_404(ProductVariant, sku=sku)
        serializer = ProductVariantSerializer(variant)
        data = serializer.data
        
        # Include stock by warehouse
        stocks = InventoryItem.objects.filter(variant=variant).select_related('warehouse')
        data['stocks'] = InventoryItemSerializer(stocks, many=True).data
        
        return Response(data)

    def patch(self, request, sku):
        variant = get_object_or_404(ProductVariant, sku=sku)
        serializer = CreateVariantSerializer(variant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ProductVariantSerializer(variant).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VariantsByProduct(APIView):
    """Get all variants for a product"""
    
    def get(self, request, product_uuid):
        variants = ProductVariant.objects.filter(product_uuid=product_uuid, is_active=True)
        serializer = ProductVariantSerializer(variants, many=True)
        return Response(serializer.data)


# ==================== Stock Views ====================

class StockList(APIView):
    """List stock levels"""
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        items = InventoryItem.objects.all().select_related('variant', 'warehouse')
        
        warehouse_code = request.query_params.get('warehouse')
        if warehouse_code:
            items = items.filter(warehouse__code=warehouse_code)
        
        low_stock = request.query_params.get('low_stock')
        if low_stock and low_stock.lower() == 'true':
            items = items.filter(quantity__lte=F('low_stock_threshold') + F('reserved_quantity'))
        
        out_of_stock = request.query_params.get('out_of_stock')
        if out_of_stock and out_of_stock.lower() == 'true':
            items = items.filter(quantity__lte=F('reserved_quantity'))
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(items, request)
        if page is not None:
            serializer = InventoryItemSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = InventoryItemSerializer(items, many=True)
        return Response(serializer.data)


class StockByVariant(APIView):
    """Get stock for a variant across all warehouses"""
    
    def get(self, request, sku):
        variant = get_object_or_404(ProductVariant, sku=sku)
        items = InventoryItem.objects.filter(variant=variant).select_related('warehouse')
        
        total = items.aggregate(
            total_quantity=Sum('quantity'),
            total_reserved=Sum('reserved_quantity')
        )
        
        return Response({
            'sku': sku,
            'variant_name': variant.name,
            'total_quantity': total['total_quantity'] or 0,
            'total_reserved': total['total_reserved'] or 0,
            'total_available': (total['total_quantity'] or 0) - (total['total_reserved'] or 0),
            'stocks': InventoryItemSerializer(items, many=True).data
        })


class StockCheck(APIView):
    """Check stock availability for multiple items"""
    
    def post(self, request):
        items = request.data.get('items', [])
        results = []
        all_available = True
        
        for item in items:
            sku = item.get('sku')
            quantity = item.get('quantity', 1)
            warehouse_code = item.get('warehouse_code')
            
            try:
                variant = ProductVariant.objects.get(sku=sku, is_active=True)
                
                if warehouse_code:
                    stock = InventoryItem.objects.filter(
                        variant=variant,
                        warehouse__code=warehouse_code
                    ).first()
                    available = stock.available_quantity if stock else 0
                else:
                    # Sum across all warehouses
                    agg = InventoryItem.objects.filter(variant=variant).aggregate(
                        total=Sum(F('quantity') - F('reserved_quantity'))
                    )
                    available = agg['total'] or 0
                
                is_available = available >= quantity
                if not is_available:
                    all_available = False
                
                results.append({
                    'sku': sku,
                    'requested': quantity,
                    'available': available,
                    'is_available': is_available
                })
            except ProductVariant.DoesNotExist:
                all_available = False
                results.append({
                    'sku': sku,
                    'requested': quantity,
                    'available': 0,
                    'is_available': False,
                    'error': 'Variant not found'
                })
        
        return Response({
            'all_available': all_available,
            'items': results
        })


class StockAdjust(APIView):
    """Manually adjust stock"""
    
    @transaction.atomic
    def post(self, request):
        serializer = StockAdjustSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        variant = get_object_or_404(ProductVariant, sku=data['sku'])
        warehouse = get_object_or_404(Warehouse, code=data['warehouse_code'])
        
        item, _ = InventoryItem.objects.get_or_create(
            variant=variant,
            warehouse=warehouse,
            defaults={'quantity': 0}
        )
        
        quantity = data['quantity']
        old_quantity = item.quantity
        new_quantity = old_quantity + quantity
        
        if new_quantity < 0:
            return Response(
                {"error": f"Insufficient stock. Current: {old_quantity}, Adjustment: {quantity}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        item.quantity = new_quantity
        item.save()
        
        # Log movement
        movement_type = 'in' if quantity > 0 else 'out'
        if 'adjustment' in data.get('reason', '').lower():
            movement_type = 'adjustment'
        
        StockMovement.objects.create(
            inventory_item=item,
            movement_type=movement_type,
            quantity=quantity,
            quantity_before=old_quantity,
            quantity_after=new_quantity,
            reference_type='manual',
            notes=data.get('reason', ''),
            created_by=data.get('created_by', 'system')
        )
        
        return Response(InventoryItemSerializer(item).data)


class InitializeStock(APIView):
    """Initialize stock for a variant"""
    
    @transaction.atomic
    def post(self, request):
        serializer = InitializeStockSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        variant = get_object_or_404(ProductVariant, sku=data['sku'])
        
        created_items = []
        for stock_data in data['stocks']:
            warehouse = get_object_or_404(Warehouse, code=stock_data['warehouse_code'])
            
            item, created = InventoryItem.objects.update_or_create(
                variant=variant,
                warehouse=warehouse,
                defaults={
                    'quantity': stock_data['quantity'],
                    'low_stock_threshold': stock_data.get('low_stock_threshold', 10)
                }
            )
            
            if created:
                StockMovement.objects.create(
                    inventory_item=item,
                    movement_type='in',
                    quantity=stock_data['quantity'],
                    quantity_before=0,
                    quantity_after=stock_data['quantity'],
                    reference_type='system',
                    notes='Initial stock setup'
                )
            
            created_items.append(item)
        
        return Response(InventoryItemSerializer(created_items, many=True).data, status=status.HTTP_201_CREATED)


# ==================== Reservation Views ====================

class ReserveStock(APIView):
    """Reserve stock for an order"""
    
    @transaction.atomic
    def post(self, request):
        serializer = ReserveStockSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        order_id = data['order_id']
        items = data['items']
        expiry_minutes = data.get('expiry_minutes', getattr(settings, 'RESERVATION_EXPIRY_MINUTES', 30))
        
        # Check all items first
        for item in items:
            sku = item.get('sku')
            quantity = item.get('quantity', 1)
            warehouse_code = item.get('warehouse_code')
            
            try:
                variant = ProductVariant.objects.get(sku=sku, is_active=True)
                
                if warehouse_code:
                    stock = InventoryItem.objects.filter(
                        variant=variant,
                        warehouse__code=warehouse_code
                    ).first()
                    if not stock or stock.available_quantity < quantity:
                        return Response({
                            'error': f'Insufficient stock for {sku}',
                            'sku': sku,
                            'available': stock.available_quantity if stock else 0,
                            'requested': quantity
                        }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Find warehouse with enough stock
                    stocks = InventoryItem.objects.filter(
                        variant=variant,
                        quantity__gt=F('reserved_quantity')
                    ).order_by('-warehouse__priority')
                    
                    total_available = sum(s.available_quantity for s in stocks)
                    if total_available < quantity:
                        return Response({
                            'error': f'Insufficient stock for {sku}',
                            'sku': sku,
                            'available': total_available,
                            'requested': quantity
                        }, status=status.HTTP_400_BAD_REQUEST)
                        
            except ProductVariant.DoesNotExist:
                return Response({
                    'error': f'Variant not found: {sku}',
                    'sku': sku
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create reservations
        reservations = []
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
        
        for item in items:
            sku = item.get('sku')
            quantity = item.get('quantity', 1)
            warehouse_code = item.get('warehouse_code')
            
            variant = ProductVariant.objects.get(sku=sku)
            
            if warehouse_code:
                stock = InventoryItem.objects.get(variant=variant, warehouse__code=warehouse_code)
                
                stock.reserved_quantity += quantity
                stock.save()
                
                reservation = StockReservation.objects.create(
                    inventory_item=stock,
                    order_id=order_id,
                    quantity=quantity,
                    expires_at=expires_at
                )
                
                StockMovement.objects.create(
                    inventory_item=stock,
                    movement_type='reserve',
                    quantity=-quantity,
                    quantity_before=stock.reserved_quantity - quantity,
                    quantity_after=stock.reserved_quantity,
                    reference_type='order',
                    reference_id=str(order_id),
                    notes=f'Reserved for order #{order_id}'
                )
                
                reservations.append(reservation)
            else:
                # Allocate from warehouses by priority
                remaining = quantity
                stocks = InventoryItem.objects.filter(
                    variant=variant,
                    quantity__gt=F('reserved_quantity')
                ).order_by('-warehouse__priority')
                
                for stock in stocks:
                    if remaining <= 0:
                        break
                    
                    available = stock.available_quantity
                    to_reserve = min(available, remaining)
                    
                    stock.reserved_quantity += to_reserve
                    stock.save()
                    
                    reservation = StockReservation.objects.create(
                        inventory_item=stock,
                        order_id=order_id,
                        quantity=to_reserve,
                        expires_at=expires_at
                    )
                    
                    StockMovement.objects.create(
                        inventory_item=stock,
                        movement_type='reserve',
                        quantity=-to_reserve,
                        quantity_before=stock.reserved_quantity - to_reserve,
                        quantity_after=stock.reserved_quantity,
                        reference_type='order',
                        reference_id=str(order_id),
                        notes=f'Reserved for order #{order_id}'
                    )
                    
                    reservations.append(reservation)
                    remaining -= to_reserve
        
        return Response({
            'order_id': order_id,
            'reservations': StockReservationSerializer(reservations, many=True).data,
            'expires_at': expires_at
        }, status=status.HTTP_201_CREATED)


class CommitReservation(APIView):
    """Commit reservations for an order (convert reserved to sold)"""
    
    @transaction.atomic
    def post(self, request, order_id):
        reservations = StockReservation.objects.filter(
            order_id=order_id,
            status='active'
        )
        
        if not reservations.exists():
            return Response({
                'error': 'No active reservations found for this order'
            }, status=status.HTTP_404_NOT_FOUND)
        
        committed = []
        for reservation in reservations:
            if reservation.commit():
                committed.append(reservation)
        
        return Response({
            'order_id': order_id,
            'committed_count': len(committed),
            'reservations': StockReservationSerializer(committed, many=True).data
        })


class ReleaseReservation(APIView):
    """Release reservations for an order (order cancelled)"""
    
    @transaction.atomic
    def post(self, request, order_id):
        reason = request.data.get('reason', 'Order cancelled')
        
        reservations = StockReservation.objects.filter(
            order_id=order_id,
            status='active'
        )
        
        if not reservations.exists():
            return Response({
                'error': 'No active reservations found for this order'
            }, status=status.HTTP_404_NOT_FOUND)
        
        released = []
        for reservation in reservations:
            if reservation.release(reason):
                released.append(reservation)
        
        return Response({
            'order_id': order_id,
            'released_count': len(released),
            'reservations': StockReservationSerializer(released, many=True).data
        })


class ReservationsByOrder(APIView):
    """Get all reservations for an order"""
    
    def get(self, request, order_id):
        reservations = StockReservation.objects.filter(order_id=order_id).select_related(
            'inventory_item__variant',
            'inventory_item__warehouse'
        )
        return Response(StockReservationSerializer(reservations, many=True).data)


# ==================== Movement Views ====================

class StockMovementList(APIView):
    """List stock movements"""
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        movements = StockMovement.objects.all().select_related(
            'inventory_item__variant',
            'inventory_item__warehouse'
        )
        
        sku = request.query_params.get('sku')
        if sku:
            movements = movements.filter(inventory_item__variant__sku=sku)
        
        warehouse = request.query_params.get('warehouse')
        if warehouse:
            movements = movements.filter(inventory_item__warehouse__code=warehouse)
        
        movement_type = request.query_params.get('type')
        if movement_type:
            movements = movements.filter(movement_type=movement_type)
        
        reference_id = request.query_params.get('reference_id')
        if reference_id:
            movements = movements.filter(reference_id=reference_id)
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(movements, request)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)


class MovementsByVariant(APIView):
    """Get movements for a specific variant"""
    pagination_class = StandardResultsSetPagination

    def get(self, request, sku):
        variant = get_object_or_404(ProductVariant, sku=sku)
        movements = StockMovement.objects.filter(
            inventory_item__variant=variant
        ).select_related('inventory_item__warehouse')
        
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(movements, request)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)


# ==================== Cleanup View ====================

class ExpireReservations(APIView):
    """Expire old reservations (called by cron/scheduler)"""
    
    @transaction.atomic
    def post(self, request):
        expired = StockReservation.objects.filter(
            status='active',
            expires_at__lt=timezone.now()
        )
        
        count = 0
        for reservation in expired:
            reservation.status = 'expired'
            reservation.released_at = timezone.now()
            
            # Release reserved quantity
            item = reservation.inventory_item
            item.reserved_quantity -= reservation.quantity
            item.save()
            
            StockMovement.objects.create(
                inventory_item=item,
                movement_type='release',
                quantity=reservation.quantity,
                quantity_before=item.reserved_quantity + reservation.quantity,
                quantity_after=item.reserved_quantity,
                reference_type='system',
                reference_id=str(reservation.order_id),
                notes=f'Auto-expired reservation {reservation.reservation_id}'
            )
            
            reservation.save()
            count += 1
        
        return Response({'expired_count': count})
