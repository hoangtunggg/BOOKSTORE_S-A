from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import ProductType, AttributeDefinition, Product, ProductAttribute, ProductImage, ProductCategory
from .serializers import (
    ProductTypeSerializer, ProductTypeListSerializer, AttributeDefinitionSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateSerializer,
    ProductSyncSerializer, BulkProductSyncSerializer,
    ProductImageSerializer, ProductAttributeSerializer, ProductCategorySerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ==================== Product Type Views ====================

class ProductTypeListCreate(APIView):
    """List all product types or create a new one"""
    
    def get(self, request):
        product_types = ProductType.objects.filter(is_active=True)
        serializer = ProductTypeListSerializer(product_types, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductTypeDetail(APIView):
    """Retrieve, update or delete a product type"""
    
    def get(self, request, code):
        product_type = get_object_or_404(ProductType, code=code)
        serializer = ProductTypeSerializer(product_type)
        return Response(serializer.data)

    def put(self, request, code):
        product_type = get_object_or_404(ProductType, code=code)
        serializer = ProductTypeSerializer(product_type, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, code):
        product_type = get_object_or_404(ProductType, code=code)
        serializer = ProductTypeSerializer(product_type, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductTypeAttributes(APIView):
    """Manage attribute definitions for a product type"""
    
    def get(self, request, code):
        product_type = get_object_or_404(ProductType, code=code)
        attributes = product_type.attribute_definitions.all()
        serializer = AttributeDefinitionSerializer(attributes, many=True)
        return Response(serializer.data)

    def post(self, request, code):
        product_type = get_object_or_404(ProductType, code=code)
        serializer = AttributeDefinitionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(product_type=product_type)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AttributeDefinitionDetail(APIView):
    """Update or delete an attribute definition"""
    
    def put(self, request, pk):
        attribute = get_object_or_404(AttributeDefinition, pk=pk)
        serializer = AttributeDefinitionSerializer(attribute, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        attribute = get_object_or_404(AttributeDefinition, pk=pk)
        attribute.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== Product Views ====================

class ProductListCreate(APIView):
    """List all products or create a new one"""
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        products = Product.objects.filter(is_active=True).select_related('product_type').prefetch_related('images')
        
        # Filters
        product_type = request.query_params.get('type')
        if product_type:
            products = products.filter(product_type__code=product_type)
        
        category_id = request.query_params.get('category')
        if category_id:
            products = products.filter(categories__category_id=category_id)
        
        min_price = request.query_params.get('min_price')
        if min_price:
            products = products.filter(Q(sale_price__gte=min_price) | Q(sale_price__isnull=True, base_price__gte=min_price))
        
        max_price = request.query_params.get('max_price')
        if max_price:
            products = products.filter(Q(sale_price__lte=max_price) | Q(sale_price__isnull=True, base_price__lte=max_price))
        
        min_rating = request.query_params.get('min_rating')
        if min_rating:
            products = products.filter(avg_rating__gte=min_rating)
        
        featured = request.query_params.get('featured')
        if featured and featured.lower() == 'true':
            products = products.filter(is_featured=True)

        search = request.query_params.get('search')
        if search:
            products = products.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Sorting
        sort = request.query_params.get('sort', '-created_at')
        sort_mapping = {
            'price_asc': 'base_price',
            'price_desc': '-base_price',
            'rating': '-avg_rating',
            'newest': '-created_at',
            'bestseller': '-sold_count',
            'name': 'name',
        }
        sort_field = sort_mapping.get(sort, sort)
        products = products.order_by(sort_field)

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(products, request)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductCreateSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductDetailSerializer(product).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductDetail(APIView):
    """Retrieve, update or delete a product"""
    
    def get(self, request, uuid):
        product = get_object_or_404(
            Product.objects.select_related('product_type').prefetch_related('attributes__attribute', 'images', 'categories'),
            uuid=uuid
        )
        # Increment view count
        product.view_count += 1
        product.save(update_fields=['view_count'])
        
        serializer = ProductDetailSerializer(product)
        return Response(serializer.data)

    def put(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        serializer = ProductDetailSerializer(product, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        serializer = ProductDetailSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        # Soft delete
        product.is_active = False
        product.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductBySlug(APIView):
    """Get product by slug"""
    
    def get(self, request, slug):
        product = get_object_or_404(
            Product.objects.select_related('product_type').prefetch_related('attributes__attribute', 'images', 'categories'),
            slug=slug,
            is_active=True
        )
        product.view_count += 1
        product.save(update_fields=['view_count'])
        
        serializer = ProductDetailSerializer(product)
        return Response(serializer.data)


class ProductsByType(APIView):
    """List products by product type"""
    pagination_class = StandardResultsSetPagination

    def get(self, request, type_code):
        product_type = get_object_or_404(ProductType, code=type_code)
        products = Product.objects.filter(
            product_type=product_type,
            is_active=True
        ).select_related('product_type').prefetch_related('images')

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(products, request)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)


# ==================== Product Attributes Views ====================

class ProductAttributeList(APIView):
    """Get or update attributes for a product"""
    
    def get(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        attributes = product.attributes.select_related('attribute').all()
        serializer = ProductAttributeSerializer(attributes, many=True)
        return Response(serializer.data)

    def post(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        attribute_id = request.data.get('attribute_id')
        value = request.data.get('value')
        
        if not attribute_id or value is None:
            return Response(
                {"error": "attribute_id and value are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attr, created = ProductAttribute.objects.update_or_create(
            product=product,
            attribute_id=attribute_id,
            defaults={'value': value}
        )
        serializer = ProductAttributeSerializer(attr)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# ==================== Product Images Views ====================

class ProductImageList(APIView):
    """Manage images for a product"""
    
    def get(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        images = product.images.all()
        serializer = ProductImageSerializer(images, many=True)
        return Response(serializer.data)

    def post(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        serializer = ProductImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductImageDetail(APIView):
    """Update or delete a product image"""
    
    def delete(self, request, uuid, image_id):
        product = get_object_or_404(Product, uuid=uuid)
        image = get_object_or_404(ProductImage, pk=image_id, product=product)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== Product Categories Views ====================

class ProductCategoryList(APIView):
    """Manage categories for a product"""
    
    def get(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        categories = product.categories.all()
        serializer = ProductCategorySerializer(categories, many=True)
        return Response(serializer.data)

    def post(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        category_id = request.data.get('category_id')
        is_primary = request.data.get('is_primary', False)
        
        if not category_id:
            return Response(
                {"error": "category_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pc, created = ProductCategory.objects.update_or_create(
            product=product,
            category_id=category_id,
            defaults={'is_primary': is_primary}
        )
        serializer = ProductCategorySerializer(pc)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        category_id = request.data.get('category_id')
        
        if not category_id:
            return Response(
                {"error": "category_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deleted, _ = ProductCategory.objects.filter(product=product, category_id=category_id).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"error": "Category not found for this product"}, status=status.HTTP_404_NOT_FOUND)


# ==================== Sync Views ====================

class ProductSync(APIView):
    """Sync a single product from specialized service"""
    
    def post(self, request):
        serializer = ProductSyncSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        product_type = get_object_or_404(ProductType, code=data['product_type_code'])
        
        # Create or update product
        product, created = Product.objects.update_or_create(
            product_type=product_type,
            external_id=data['external_id'],
            defaults={
                'name': data['name'],
                'description': data.get('description', ''),
                'base_price': data['base_price'],
                'sale_price': data.get('sale_price'),
                'is_active': data.get('is_active', True),
            }
        )
        
        # Sync attributes
        attributes = data.get('attributes', {})
        for attr_name, value in attributes.items():
            try:
                attr_def = AttributeDefinition.objects.get(product_type=product_type, name=attr_name)
                ProductAttribute.objects.update_or_create(
                    product=product,
                    attribute=attr_def,
                    defaults={'value': value}
                )
            except AttributeDefinition.DoesNotExist:
                pass  # Skip unknown attributes
        
        # Sync images
        images = data.get('images', [])
        if images:
            # Clear existing and add new
            product.images.all().delete()
            for idx, url in enumerate(images):
                ProductImage.objects.create(
                    product=product,
                    url=url,
                    position=idx,
                    is_primary=(idx == 0)
                )
        
        # Sync categories
        category_ids = data.get('category_ids', [])
        if category_ids:
            product.categories.all().delete()
            for idx, cat_id in enumerate(category_ids):
                ProductCategory.objects.create(
                    product=product,
                    category_id=cat_id,
                    is_primary=(idx == 0)
                )
        
        response_serializer = ProductDetailSerializer(product)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class BulkProductSync(APIView):
    """Bulk sync products from specialized services"""
    
    def post(self, request):
        serializer = BulkProductSyncSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        results = {'created': 0, 'updated': 0, 'errors': []}
        
        for product_data in serializer.validated_data['products']:
            try:
                product_type = ProductType.objects.get(code=product_data['product_type_code'])
                
                product, created = Product.objects.update_or_create(
                    product_type=product_type,
                    external_id=product_data['external_id'],
                    defaults={
                        'name': product_data['name'],
                        'description': product_data.get('description', ''),
                        'base_price': product_data['base_price'],
                        'sale_price': product_data.get('sale_price'),
                        'is_active': product_data.get('is_active', True),
                    }
                )
                
                # Sync attributes
                attributes = product_data.get('attributes', {})
                for attr_name, value in attributes.items():
                    try:
                        attr_def = AttributeDefinition.objects.get(product_type=product_type, name=attr_name)
                        ProductAttribute.objects.update_or_create(
                            product=product,
                            attribute=attr_def,
                            defaults={'value': value}
                        )
                    except AttributeDefinition.DoesNotExist:
                        pass
                
                if created:
                    results['created'] += 1
                else:
                    results['updated'] += 1
                    
            except ProductType.DoesNotExist:
                results['errors'].append({
                    'external_id': product_data['external_id'],
                    'error': f"Product type '{product_data['product_type_code']}' not found"
                })
            except Exception as e:
                results['errors'].append({
                    'external_id': product_data['external_id'],
                    'error': str(e)
                })
        
        return Response(results)


class ProductUpdateStats(APIView):
    """Update product stats (called by other services)"""
    
    def post(self, request, uuid):
        product = get_object_or_404(Product, uuid=uuid)
        
        if 'avg_rating' in request.data:
            product.avg_rating = request.data['avg_rating']
        if 'review_count' in request.data:
            product.review_count = request.data['review_count']
        if 'sold_count' in request.data:
            product.sold_count = request.data['sold_count']
        
        product.save()
        return Response({'success': True})


class ProductByExternalId(APIView):
    """Get product by type code and external ID"""
    
    def get(self, request, type_code, external_id):
        product = get_object_or_404(
            Product.objects.select_related('product_type').prefetch_related('attributes__attribute', 'images', 'categories'),
            product_type__code=type_code,
            external_id=external_id
        )
        serializer = ProductDetailSerializer(product)
        return Response(serializer.data)
