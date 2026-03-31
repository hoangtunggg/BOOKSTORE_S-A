from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Cart, CartItem
from .serializers import CartSerializer, CartItemSerializer, CartItemCreateSerializer, CartWithItemsSerializer
import requests
import os

BOOK_SERVICE_URL = os.environ.get("BOOK_SERVICE_URL", "http://book-service:8000")
CLOTHE_SERVICE_URL = os.environ.get("CLOTHE_SERVICE_URL", "http://clothe-service:8000")
PRODUCT_CORE_SERVICE_URL = os.environ.get("PRODUCT_CORE_SERVICE_URL", "http://product-core-service:8000")
INVENTORY_SERVICE_URL = os.environ.get("INVENTORY_SERVICE_URL", "http://inventory-service:8000")


class CartCreate(APIView):
    def post(self, request):
        serializer = CartSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors)


class AddCartItem(APIView):
    """Add item to cart - supports both book_id and product_uuid"""
    
    def post(self, request):
        serializer = CartItemCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        cart_id = data['cart']
        quantity = data['quantity']
        book_id = data.get('book_id')
        product_uuid = data.get('product_uuid')
        variant_sku = data.get('variant_sku')
        
        if not Cart.objects.filter(id=cart_id).exists():
            return Response({"error": "Cart not found"}, status=status.HTTP_404_NOT_FOUND)
        
        product_info = {}
        
        # Handle product_uuid (new unified approach)
        if product_uuid:
            try:
                # Get product info from Product Core Service
                r = requests.get(f"{PRODUCT_CORE_SERVICE_URL}/products/{product_uuid}/", timeout=3)
                if r.status_code != 200:
                    return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
                
                product_data = r.json()
                product_info = {
                    'product_name': product_data.get('name', ''),
                    'product_type': product_data.get('product_type', {}).get('code', ''),
                    'unit_price': product_data.get('sale_price') or product_data.get('base_price'),
                    'thumbnail_url': product_data.get('primary_image', '') or '',
                }
                
                # Check stock from Inventory Service (if variant_sku provided)
                if variant_sku:
                    r = requests.post(f"{INVENTORY_SERVICE_URL}/stock/check/", json={
                        'items': [{'sku': variant_sku, 'quantity': quantity}]
                    }, timeout=3)
                    if r.status_code == 200:
                        check_result = r.json()
                        if not check_result.get('all_available'):
                            return Response({
                                "error": "Insufficient stock",
                                "details": check_result.get('items', [])
                            }, status=status.HTTP_400_BAD_REQUEST)
                
                # Check for existing item and merge
                existing = CartItem.objects.filter(
                    cart_id=cart_id, 
                    product_uuid=product_uuid,
                    variant_sku=variant_sku
                ).first()
                
                if existing:
                    merged_quantity = existing.quantity + quantity
                    # Re-check stock for merged quantity
                    if variant_sku:
                        r = requests.post(f"{INVENTORY_SERVICE_URL}/stock/check/", json={
                            'items': [{'sku': variant_sku, 'quantity': merged_quantity}]
                        }, timeout=3)
                        if r.status_code == 200:
                            check_result = r.json()
                            if not check_result.get('all_available'):
                                return Response({
                                    "error": "Insufficient stock for requested quantity"
                                }, status=status.HTTP_400_BAD_REQUEST)
                    
                    existing.quantity = merged_quantity
                    existing.save(update_fields=['quantity', 'updated_at'])
                    return Response(CartItemSerializer(existing).data, status=status.HTTP_200_OK)
                
                # Create new item
                item = CartItem.objects.create(
                    cart_id=cart_id,
                    product_uuid=product_uuid,
                    variant_sku=variant_sku,
                    quantity=quantity,
                    **product_info
                )
                return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)
                
            except requests.exceptions.RequestException:
                # Graceful degradation - allow adding without full validation
                pass
        
        # Handle book_id (backward compatible)
        if book_id:
            try:
                if book_id > 1000000:
                    # Clothe
                    real_id = book_id - 1000000
                    r = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/{real_id}/", timeout=3)
                    if r.status_code != 200:
                        return Response({"error": "Clothe not found"}, status=status.HTTP_404_NOT_FOUND)
                    item_data = r.json()
                    product_info = {
                        'product_name': item_data.get('name', ''),
                        'product_type': 'clothing',
                        'unit_price': item_data.get('price'),
                    }
                else:
                    # Book
                    r = requests.get(f"{BOOK_SERVICE_URL}/books/{book_id}/", timeout=3)
                    if r.status_code != 200:
                        return Response({"error": "Book not found"}, status=status.HTTP_404_NOT_FOUND)
                    item_data = r.json()
                    product_info = {
                        'product_name': item_data.get('title', ''),
                        'product_type': 'book',
                        'unit_price': item_data.get('price'),
                    }
                
                if int(item_data.get("stock", 0) or 0) < quantity:
                    return Response({"error": "Insufficient stock"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Merge duplicates
                existing = CartItem.objects.filter(cart_id=cart_id, book_id=book_id).first()
                if existing:
                    merged_quantity = existing.quantity + quantity
                    if int(item_data.get("stock", 0) or 0) < merged_quantity:
                        return Response({"error": "Insufficient stock for requested quantity"}, status=status.HTTP_400_BAD_REQUEST)
                    existing.quantity = merged_quantity
                    existing.save(update_fields=["quantity", "updated_at"])
                    return Response(CartItemSerializer(existing).data, status=status.HTTP_200_OK)
                    
            except requests.exceptions.RequestException:
                # Graceful degradation
                pass
            
            item = CartItem.objects.create(
                cart_id=cart_id,
                book_id=book_id,
                quantity=quantity,
                **product_info
            )
            return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)
        
        return Response({"error": "Either book_id or product_uuid is required"}, status=status.HTTP_400_BAD_REQUEST)


class UpdateCartItemQuantity(APIView):
    """Update quantity of a cart item"""
    
    def patch(self, request, item_id):
        try:
            item = CartItem.objects.get(id=item_id)
            quantity = request.data.get('quantity')
            
            if quantity is None:
                return Response({"error": "quantity is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            quantity = int(quantity)
            if quantity <= 0:
                item.delete()
                return Response({"message": "Item removed from cart"}, status=status.HTTP_200_OK)
            
            item.quantity = quantity
            item.save(update_fields=['quantity', 'updated_at'])
            return Response(CartItemSerializer(item).data)
            
        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"error": "Invalid quantity"}, status=status.HTTP_400_BAD_REQUEST)


class DeleteCartItem(APIView):
    """Delete item from cart by book_id (backward compatible)"""
    
    def delete(self, request, cart_id, book_id):
        deleted, _ = CartItem.objects.filter(cart_id=cart_id, book_id=book_id).delete()
        if deleted:
            return Response({"message": "Item removed from cart"})
        return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)


class DeleteCartItemByProduct(APIView):
    """Delete item from cart by product_uuid"""
    
    def delete(self, request, cart_id, product_uuid):
        variant_sku = request.query_params.get('variant_sku')
        
        queryset = CartItem.objects.filter(cart_id=cart_id, product_uuid=product_uuid)
        if variant_sku:
            queryset = queryset.filter(variant_sku=variant_sku)
        
        deleted, _ = queryset.delete()
        if deleted:
            return Response({"message": "Item(s) removed from cart"})
        return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)


class ClearCart(APIView):
    """Clear all items from a customer's cart"""
    
    def delete(self, request, customer_id):
        try:
            cart = Cart.objects.get(customer_id=customer_id)
            deleted_count, _ = CartItem.objects.filter(cart=cart).delete()
            return Response({"message": f"Cart cleared. {deleted_count} items removed."})
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found"}, status=status.HTTP_404_NOT_FOUND)


class CartView(APIView):
    """Get cart with all items for a customer"""
    
    def get(self, request, customer_id):
        try:
            cart, created = Cart.objects.get_or_create(customer_id=customer_id)
            serializer = CartWithItemsSerializer(cart)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CartItemDetail(APIView):
    """Get, update or delete a specific cart item"""
    
    def get(self, request, item_id):
        try:
            item = CartItem.objects.get(id=item_id)
            return Response(CartItemSerializer(item).data)
        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, item_id):
        try:
            item = CartItem.objects.get(id=item_id)
            item.delete()
            return Response({"message": "Item removed from cart"})
        except CartItem.DoesNotExist:
            return Response({"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND)