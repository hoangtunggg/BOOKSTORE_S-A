from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Category, BookCatalog, ProductCatalog, CategoryProductType
from .serializers import (
    CategorySerializer, CategoryListSerializer, CategoryTreeSerializer, CategoryDetailSerializer,
    BookCatalogSerializer, ProductCatalogSerializer, CategoryProductTypeSerializer
)


class CategoryListCreate(APIView):
    """List all categories or create a new one"""
    
    def get(self, request):
        # Filter options
        parent_id = request.query_params.get('parent')
        is_root = request.query_params.get('root')
        is_active = request.query_params.get('active', 'true').lower() == 'true'
        is_featured = request.query_params.get('featured')
        
        categories = Category.objects.all()
        
        if is_active:
            categories = categories.filter(is_active=True)
        
        if parent_id:
            categories = categories.filter(parent_id=parent_id)
        elif is_root and is_root.lower() == 'true':
            categories = categories.filter(parent__isnull=True)
        
        if is_featured and is_featured.lower() == 'true':
            categories = categories.filter(is_featured=True)
        
        categories = categories.order_by('position', 'name')
        return Response(CategoryListSerializer(categories, many=True).data)

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetail(APIView):
    """Retrieve, update or delete a category"""
    
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        data = CategoryDetailSerializer(category).data
        
        # Include product IDs
        include_descendants = request.query_params.get('include_descendants', 'false').lower() == 'true'
        product_ids = category.get_all_product_ids(include_descendants=include_descendants)
        data['book_ids'] = product_ids['book_ids']
        data['product_uuids'] = product_ids['product_uuids']
        
        return Response(data)

    def put(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        serializer = CategorySerializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        # Soft delete
        category.is_active = False
        category.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryBySlug(APIView):
    """Get category by slug"""
    
    def get(self, request, slug):
        category = get_object_or_404(Category, slug=slug, is_active=True)
        data = CategoryDetailSerializer(category).data
        
        include_descendants = request.query_params.get('include_descendants', 'false').lower() == 'true'
        product_ids = category.get_all_product_ids(include_descendants=include_descendants)
        data['book_ids'] = product_ids['book_ids']
        data['product_uuids'] = product_ids['product_uuids']
        
        return Response(data)


class CategoryTree(APIView):
    """Get full category tree"""
    
    def get(self, request):
        # Get root categories
        root_categories = Category.objects.filter(
            parent__isnull=True, 
            is_active=True
        ).order_by('position', 'name')
        
        return Response(CategoryTreeSerializer(root_categories, many=True).data)


class CategoryChildren(APIView):
    """Get direct children of a category"""
    
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        children = category.children.filter(is_active=True).order_by('position', 'name')
        return Response(CategoryListSerializer(children, many=True).data)


class CategoryAncestors(APIView):
    """Get ancestor path of a category"""
    
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        ancestors = category.get_ancestors()
        return Response(CategoryListSerializer(ancestors, many=True).data)


class CategoryDescendants(APIView):
    """Get all descendants of a category"""
    
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        descendants = category.get_descendants()
        return Response(CategoryListSerializer(descendants, many=True).data)


class CategoryAllowedTypes(APIView):
    """Manage allowed product types for a category"""
    
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        types = category.allowed_types.all()
        return Response(CategoryProductTypeSerializer(types, many=True).data)

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        product_type_code = request.data.get('product_type_code')
        
        if not product_type_code:
            return Response(
                {"error": "product_type_code is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        type_obj, created = CategoryProductType.objects.get_or_create(
            category=category,
            product_type_code=product_type_code
        )
        return Response(
            CategoryProductTypeSerializer(type_obj).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def delete(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        product_type_code = request.data.get('product_type_code')
        
        if not product_type_code:
            return Response(
                {"error": "product_type_code is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deleted, _ = CategoryProductType.objects.filter(
            category=category, 
            product_type_code=product_type_code
        ).delete()
        
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"error": "Product type not found"}, status=status.HTTP_404_NOT_FOUND)


class BookCatalogListCreate(APIView):
    """List/create book-category mappings (backward compatible)"""
    
    def get(self, request):
        book_id = request.query_params.get('book_id')
        category_id = request.query_params.get('category')
        
        items = BookCatalog.objects.all().select_related('category')
        
        if book_id:
            items = items.filter(book_id=book_id)
        if category_id:
            items = items.filter(category_id=category_id)
        
        return Response(BookCatalogSerializer(items, many=True).data)

    def post(self, request):
        serializer = BookCatalogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookCatalogDelete(APIView):
    """Delete a book-category mapping"""
    
    def delete(self, request, book_id, category_id):
        deleted, _ = BookCatalog.objects.filter(book_id=book_id, category_id=category_id).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"error": "Mapping not found"}, status=status.HTTP_404_NOT_FOUND)


class ProductCatalogListCreate(APIView):
    """List/create product-category mappings (new unified approach)"""
    
    def get(self, request):
        product_uuid = request.query_params.get('product_uuid')
        category_id = request.query_params.get('category')
        
        items = ProductCatalog.objects.all().select_related('category')
        
        if product_uuid:
            items = items.filter(product_uuid=product_uuid)
        if category_id:
            items = items.filter(category_id=category_id)
        
        return Response(ProductCatalogSerializer(items, many=True).data)

    def post(self, request):
        serializer = ProductCatalogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductCatalogDelete(APIView):
    """Delete a product-category mapping"""
    
    def delete(self, request, product_uuid, category_id):
        deleted, _ = ProductCatalog.objects.filter(
            product_uuid=product_uuid, 
            category_id=category_id
        ).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"error": "Mapping not found"}, status=status.HTTP_404_NOT_FOUND)


class CategoryProducts(APIView):
    """Get products in a category"""
    
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        include_descendants = request.query_params.get('include_descendants', 'false').lower() == 'true'
        
        return Response(category.get_all_product_ids(include_descendants=include_descendants))


class UpdateProductCount(APIView):
    """Update product count for a category (called internally)"""
    
    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        
        # Count books and products
        book_count = category.books.count()
        product_count = category.products.count()
        
        category.product_count = book_count + product_count
        category.save(update_fields=['product_count'])
        
        return Response({'product_count': category.product_count})
