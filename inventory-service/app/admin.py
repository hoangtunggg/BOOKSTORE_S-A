from django.contrib import admin
from .models import Warehouse, ProductVariant, InventoryItem, StockMovement, StockReservation


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'city', 'is_active', 'priority']
    list_filter = ['is_active', 'city']
    search_fields = ['code', 'name', 'city']


class InventoryItemInline(admin.TabularInline):
    model = InventoryItem
    extra = 0
    readonly_fields = ['available_quantity']

    def available_quantity(self, obj):
        return obj.available_quantity


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'product_uuid', 'is_active', 'get_total_stock']
    list_filter = ['is_active']
    search_fields = ['sku', 'name', 'barcode']
    inlines = [InventoryItemInline]

    def get_total_stock(self, obj):
        return obj.get_total_stock()
    get_total_stock.short_description = 'Total Stock'


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ['variant', 'warehouse', 'quantity', 'reserved_quantity', 'available_quantity', 'is_low_stock']
    list_filter = ['warehouse']
    search_fields = ['variant__sku', 'variant__name']

    def available_quantity(self, obj):
        return obj.available_quantity

    def is_low_stock(self, obj):
        return obj.is_low_stock
    is_low_stock.boolean = True


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['inventory_item', 'movement_type', 'quantity', 'reference_type', 'reference_id', 'created_at']
    list_filter = ['movement_type', 'reference_type', 'created_at']
    search_fields = ['inventory_item__variant__sku', 'reference_id']
    readonly_fields = ['created_at']


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ['reservation_id', 'order_id', 'inventory_item', 'quantity', 'status', 'expires_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['reservation_id', 'order_id', 'inventory_item__variant__sku']
    readonly_fields = ['reservation_id', 'created_at']
