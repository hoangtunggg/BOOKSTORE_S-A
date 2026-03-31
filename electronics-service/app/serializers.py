from rest_framework import serializers
from .models import Electronic, ElectronicVariant


class ElectronicVariantSerializer(serializers.ModelSerializer):
    final_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ElectronicVariant
        fields = ['id', 'name', 'sku', 'color', 'storage', 'ram', 
                  'price_modifier', 'final_price', 'stock', 'is_active', 'created_at']


class ElectronicListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing"""
    current_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)
    variant_count = serializers.SerializerMethodField()

    class Meta:
        model = Electronic
        fields = ['id', 'name', 'brand', 'model_number', 'sub_category',
                  'price', 'sale_price', 'current_price', 'discount_percent',
                  'stock', 'thumbnail', 'is_active', 'is_featured', 'variant_count', 'created_at']

    def get_variant_count(self, obj):
        return obj.variants.filter(is_active=True).count()


class ElectronicDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail view"""
    current_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)
    variants = ElectronicVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Electronic
        fields = ['id', 'name', 'brand', 'model_number', 'sub_category',
                  'price', 'sale_price', 'current_price', 'discount_percent',
                  'stock', 'warranty_months', 'specifications',
                  'description', 'short_description',
                  'thumbnail', 'images', 'variants',
                  'is_active', 'is_featured', 'created_at', 'updated_at']


class ElectronicCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating electronics"""
    class Meta:
        model = Electronic
        fields = ['name', 'brand', 'model_number', 'sub_category',
                  'price', 'sale_price', 'stock', 'warranty_months', 'specifications',
                  'description', 'short_description', 'thumbnail', 'images',
                  'is_active', 'is_featured']


class ElectronicVariantCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating variants"""
    class Meta:
        model = ElectronicVariant
        fields = ['electronic', 'name', 'sku', 'color', 'storage', 'ram',
                  'price_modifier', 'stock', 'is_active']
