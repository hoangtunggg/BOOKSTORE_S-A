from rest_framework import serializers
from .models import Warehouse, ProductVariant, InventoryItem, StockMovement, StockReservation


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'code', 'name', 'address', 'city', 'province', 
                  'is_active', 'priority', 'created_at', 'updated_at']


class WarehouseListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'code', 'name', 'city', 'is_active', 'priority']


class ProductVariantSerializer(serializers.ModelSerializer):
    total_stock = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductVariant
        fields = ['id', 'product_uuid', 'sku', 'name', 'attributes', 'barcode',
                  'price_modifier', 'weight', 'is_active', 'total_stock', 'created_at', 'updated_at']

    def get_total_stock(self, obj):
        return obj.get_total_stock()


class ProductVariantListSerializer(serializers.ModelSerializer):
    total_stock = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductVariant
        fields = ['id', 'product_uuid', 'sku', 'name', 'attributes', 'is_active', 'total_stock']

    def get_total_stock(self, obj):
        return obj.get_total_stock()


class InventoryItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = ['id', 'variant', 'variant_sku', 'variant_name', 
                  'warehouse', 'warehouse_code', 'warehouse_name',
                  'quantity', 'reserved_quantity', 'available_quantity',
                  'low_stock_threshold', 'is_low_stock', 'is_out_of_stock', 'updated_at']


class StockMovementSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source='inventory_item.variant.sku', read_only=True)
    warehouse_code = serializers.CharField(source='inventory_item.warehouse.code', read_only=True)

    class Meta:
        model = StockMovement
        fields = ['id', 'inventory_item', 'variant_sku', 'warehouse_code',
                  'movement_type', 'quantity', 'quantity_before', 'quantity_after',
                  'reference_type', 'reference_id', 'notes', 'created_by', 'created_at']
        read_only_fields = ['quantity_before', 'quantity_after']


class StockReservationSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source='inventory_item.variant.sku', read_only=True)
    warehouse_code = serializers.CharField(source='inventory_item.warehouse.code', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = StockReservation
        fields = ['id', 'reservation_id', 'inventory_item', 'variant_sku', 'warehouse_code',
                  'order_id', 'quantity', 'status', 'is_expired',
                  'expires_at', 'committed_at', 'released_at', 'created_at']


# ==================== Request Serializers ====================

class StockAdjustSerializer(serializers.Serializer):
    """Serializer for stock adjustment"""
    sku = serializers.CharField()
    warehouse_code = serializers.CharField()
    quantity = serializers.IntegerField(help_text="Positive for adding, negative for removing")
    reason = serializers.CharField(required=False, allow_blank=True)
    created_by = serializers.CharField(required=False, allow_blank=True)


class StockCheckSerializer(serializers.Serializer):
    """Serializer for checking stock availability"""
    items = serializers.ListField(
        child=serializers.DictField()
    )


class StockCheckItemSerializer(serializers.Serializer):
    sku = serializers.CharField()
    quantity = serializers.IntegerField()
    warehouse_code = serializers.CharField(required=False)


class ReserveStockSerializer(serializers.Serializer):
    """Serializer for reserving stock"""
    order_id = serializers.IntegerField()
    items = serializers.ListField(
        child=serializers.DictField()
    )
    expiry_minutes = serializers.IntegerField(required=False)


class ReserveStockItemSerializer(serializers.Serializer):
    sku = serializers.CharField()
    quantity = serializers.IntegerField()
    warehouse_code = serializers.CharField(required=False)


class CreateVariantSerializer(serializers.ModelSerializer):
    """Serializer for creating variants"""
    class Meta:
        model = ProductVariant
        fields = ['product_uuid', 'sku', 'name', 'attributes', 'barcode',
                  'price_modifier', 'weight', 'is_active']


class InitializeStockSerializer(serializers.Serializer):
    """Serializer for initializing stock for a variant"""
    sku = serializers.CharField()
    stocks = serializers.ListField(
        child=serializers.DictField()
    )


class StockItemInitSerializer(serializers.Serializer):
    warehouse_code = serializers.CharField()
    quantity = serializers.IntegerField()
    low_stock_threshold = serializers.IntegerField(required=False, default=10)
