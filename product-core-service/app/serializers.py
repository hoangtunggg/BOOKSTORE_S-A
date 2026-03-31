from rest_framework import serializers
from .models import ProductType, AttributeDefinition, Product, ProductAttribute, ProductImage, ProductCategory


class AttributeDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttributeDefinition
        fields = ['id', 'name', 'display_name', 'data_type', 'is_required', 
                  'is_filterable', 'is_variant', 'options', 'default_value', 'position']


class ProductTypeSerializer(serializers.ModelSerializer):
    attribute_definitions = AttributeDefinitionSerializer(many=True, read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductType
        fields = ['id', 'code', 'name', 'description', 'service_url', 'icon', 
                  'is_active', 'attribute_definitions', 'product_count', 'created_at', 'updated_at']

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductTypeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing product types"""
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductType
        fields = ['id', 'code', 'name', 'icon', 'is_active', 'product_count']

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'url', 'alt_text', 'position', 'is_primary']


class ProductAttributeSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_display_name = serializers.CharField(source='attribute.display_name', read_only=True)
    data_type = serializers.CharField(source='attribute.data_type', read_only=True)

    class Meta:
        model = ProductAttribute
        fields = ['id', 'attribute', 'attribute_name', 'attribute_display_name', 'data_type', 'value']


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'category_id', 'is_primary']


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing products"""
    product_type_code = serializers.CharField(source='product_type.code', read_only=True)
    product_type_name = serializers.CharField(source='product_type.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    current_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = ['uuid', 'name', 'slug', 'short_description', 'product_type_code', 'product_type_name',
                  'base_price', 'sale_price', 'current_price', 'discount_percent',
                  'avg_rating', 'review_count', 'sold_count', 'primary_image',
                  'is_active', 'is_featured', 'created_at']

    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return primary.url
        first_image = obj.images.first()
        return first_image.url if first_image else None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full serializer for product detail"""
    product_type = ProductTypeListSerializer(read_only=True)
    product_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductType.objects.all(),
        source='product_type',
        write_only=True
    )
    attributes = ProductAttributeSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    categories = ProductCategorySerializer(many=True, read_only=True)
    current_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = ['uuid', 'name', 'slug', 'description', 'short_description',
                  'product_type', 'product_type_id', 'external_id',
                  'base_price', 'sale_price', 'current_price', 'discount_percent',
                  'is_active', 'is_featured',
                  'meta_title', 'meta_description',
                  'avg_rating', 'review_count', 'sold_count', 'view_count',
                  'attributes', 'images', 'categories',
                  'created_at', 'updated_at']
        read_only_fields = ['uuid', 'slug', 'avg_rating', 'review_count', 'sold_count', 'view_count']


class ProductCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating products"""
    product_type_code = serializers.SlugRelatedField(
        slug_field='code',
        queryset=ProductType.objects.all(),
        source='product_type'
    )
    attributes = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    images = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Product
        fields = ['name', 'description', 'short_description', 'product_type_code', 'external_id',
                  'base_price', 'sale_price', 'is_active', 'is_featured',
                  'meta_title', 'meta_description',
                  'attributes', 'images', 'category_ids']

    def create(self, validated_data):
        attributes_data = validated_data.pop('attributes', [])
        images_data = validated_data.pop('images', [])
        category_ids = validated_data.pop('category_ids', [])

        product = Product.objects.create(**validated_data)

        # Create attributes
        for attr_data in attributes_data:
            attribute_id = attr_data.get('attribute_id') or attr_data.get('attribute')
            value = attr_data.get('value')
            if attribute_id and value is not None:
                ProductAttribute.objects.create(
                    product=product,
                    attribute_id=attribute_id,
                    value=value
                )

        # Create images
        for idx, img_data in enumerate(images_data):
            ProductImage.objects.create(
                product=product,
                url=img_data.get('url'),
                alt_text=img_data.get('alt_text', ''),
                position=img_data.get('position', idx),
                is_primary=img_data.get('is_primary', idx == 0)
            )

        # Create category associations
        for idx, cat_id in enumerate(category_ids):
            ProductCategory.objects.create(
                product=product,
                category_id=cat_id,
                is_primary=(idx == 0)
            )

        return product


class ProductSyncSerializer(serializers.Serializer):
    """Serializer for syncing products from specialized services"""
    product_type_code = serializers.CharField()
    external_id = serializers.IntegerField()
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    base_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    sale_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    attributes = serializers.DictField(required=False)
    images = serializers.ListField(child=serializers.URLField(), required=False)
    category_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class BulkProductSyncSerializer(serializers.Serializer):
    """Serializer for bulk syncing products"""
    products = ProductSyncSerializer(many=True)
