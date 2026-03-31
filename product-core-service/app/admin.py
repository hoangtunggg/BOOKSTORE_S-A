from django.contrib import admin
from .models import ProductType, AttributeDefinition, Product, ProductAttribute, ProductImage, ProductCategory


class AttributeDefinitionInline(admin.TabularInline):
    model = AttributeDefinition
    extra = 1


@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['code', 'name']
    inlines = [AttributeDefinitionInline]


@admin.register(AttributeDefinition)
class AttributeDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_type', 'data_type', 'is_required', 'is_filterable', 'is_variant']
    list_filter = ['product_type', 'data_type', 'is_required', 'is_filterable', 'is_variant']
    search_fields = ['name', 'display_name']


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductCategoryInline(admin.TabularInline):
    model = ProductCategory
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_type', 'base_price', 'sale_price', 'is_active', 'is_featured', 'avg_rating', 'sold_count']
    list_filter = ['product_type', 'is_active', 'is_featured']
    search_fields = ['name', 'description', 'slug']
    readonly_fields = ['uuid', 'slug', 'avg_rating', 'review_count', 'sold_count', 'view_count', 'created_at', 'updated_at']
    inlines = [ProductAttributeInline, ProductImageInline, ProductCategoryInline]


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ['product', 'attribute', 'value']
    list_filter = ['attribute']
    search_fields = ['product__name']


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'url', 'position', 'is_primary']
    list_filter = ['is_primary']
    search_fields = ['product__name']


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'category_id', 'is_primary']
    list_filter = ['is_primary']
    search_fields = ['product__name']
