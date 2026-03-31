from rest_framework import serializers
from .models import Category, BookCatalog, ProductCatalog, CategoryProductType


class CategoryProductTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryProductType
        fields = ['id', 'product_type_code']


class CategorySerializer(serializers.ModelSerializer):
    allowed_types = CategoryProductTypeSerializer(many=True, read_only=True)
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'level', 'path',
                  'image_url', 'icon', 'position', 'is_active', 'is_featured',
                  'product_count', 'allowed_types', 'children_count', 'created_at', 'updated_at']
        read_only_fields = ['slug', 'level', 'path']

    def get_children_count(self, obj):
        return obj.children.filter(is_active=True).count()


class CategoryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing categories"""
    children_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'level', 'icon', 
                  'is_active', 'is_featured', 'product_count', 'children_count', 'position']

    def get_children_count(self, obj):
        return obj.children.filter(is_active=True).count()


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Serializer for category tree structure"""
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'level', 'product_count', 
                  'is_active', 'is_featured', 'position', 'children']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True).order_by('position', 'name')
        return CategoryTreeSerializer(children, many=True).data


class CategoryDetailSerializer(serializers.ModelSerializer):
    """Full serializer for category detail"""
    allowed_types = CategoryProductTypeSerializer(many=True, read_only=True)
    ancestors = serializers.SerializerMethodField()
    children = CategoryListSerializer(many=True, read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'level', 'path',
                  'image_url', 'icon', 'position', 'is_active', 'is_featured',
                  'product_count', 'allowed_types', 'ancestors', 'children', 
                  'created_at', 'updated_at']
        read_only_fields = ['slug', 'level', 'path']

    def get_ancestors(self, obj):
        ancestors = obj.get_ancestors()
        return CategoryListSerializer(ancestors, many=True).data


class BookCatalogSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)

    class Meta:
        model = BookCatalog
        fields = ['id', 'book_id', 'category', 'category_name', 'category_slug']


class ProductCatalogSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)

    class Meta:
        model = ProductCatalog
        fields = ['id', 'product_uuid', 'category', 'category_name', 'category_slug', 'is_primary', 'created_at']
