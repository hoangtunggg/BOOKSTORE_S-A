from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'book_id', 'product_uuid', 'variant_sku',
                  'product_name', 'product_type', 'product_thumbnail',
                  'quantity', 'unit_price', 'total_price',
                  'variant_name', 'variant_attributes', 'created_at']


class OrderItemCreateSerializer(serializers.Serializer):
    """Serializer for creating order items"""
    book_id = serializers.IntegerField(required=False, allow_null=True)
    product_uuid = serializers.UUIDField(required=False, allow_null=True)
    variant_sku = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    product_name = serializers.CharField(max_length=255)
    product_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    product_thumbnail = serializers.URLField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    variant_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    variant_attributes = serializers.DictField(required=False)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'customer_id',
                  'subtotal', 'discount_amount', 'total_price', 'shipping_fee', 'grand_total',
                  'status', 'payment_method', 'payment_status',
                  'shipping_address', 'shipping_name', 'shipping_phone', 'tracking_number',
                  'customer_note', 'admin_note',
                  'items', 'created_at', 'updated_at',
                  'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at']
        read_only_fields = ['order_number', 'created_at', 'updated_at']


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing"""
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'customer_id', 'grand_total',
                  'status', 'payment_status', 'item_count', 'created_at']

    def get_item_count(self, obj):
        return obj.items.count()


class OrderCreateSerializer(serializers.Serializer):
    """Serializer for creating orders"""
    customer_id = serializers.IntegerField()
    items = OrderItemCreateSerializer(many=True)
    shipping_address = serializers.CharField()
    shipping_name = serializers.CharField(required=False, allow_blank=True)
    shipping_phone = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=['cod', 'bank_transfer', 'e_wallet'], default='cod')
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    customer_note = serializers.CharField(required=False, allow_blank=True)
