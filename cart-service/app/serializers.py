from rest_framework import serializers
from .models import Cart, CartItem


class CartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cart
        fields = ['id', 'customer_id', 'created_at', 'updated_at']


class CartItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'cart', 'book_id', 'product_uuid', 'variant_sku', 'quantity',
                  'unit_price', 'product_name', 'product_type', 'thumbnail_url',
                  'total_price', 'created_at', 'updated_at']


class CartItemCreateSerializer(serializers.Serializer):
    """Serializer for adding items to cart"""
    cart = serializers.IntegerField()
    
    # Either book_id OR product_uuid
    book_id = serializers.IntegerField(required=False, allow_null=True)
    product_uuid = serializers.UUIDField(required=False, allow_null=True)
    variant_sku = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if not data.get('book_id') and not data.get('product_uuid'):
            raise serializers.ValidationError("Either book_id or product_uuid is required")
        return data


class CartWithItemsSerializer(serializers.ModelSerializer):
    """Full cart with items"""
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'customer_id', 'items', 'total_items', 'total_price', 'created_at', 'updated_at']

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_total_price(self, obj):
        total = sum(
            (item.unit_price or 0) * item.quantity 
            for item in obj.items.all() 
            if item.unit_price
        )
        return str(total)
