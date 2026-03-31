from django.contrib import admin
from .models import Electronic, ElectronicVariant


class ElectronicVariantInline(admin.TabularInline):
    model = ElectronicVariant
    extra = 1


@admin.register(Electronic)
class ElectronicAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand', 'sub_category', 'price', 'sale_price', 'stock', 'is_active', 'is_featured']
    list_filter = ['brand', 'sub_category', 'is_active', 'is_featured']
    search_fields = ['name', 'brand', 'model_number']
    inlines = [ElectronicVariantInline]


@admin.register(ElectronicVariant)
class ElectronicVariantAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'electronic', 'color', 'storage', 'stock', 'is_active']
    list_filter = ['is_active', 'color']
    search_fields = ['sku', 'name']
