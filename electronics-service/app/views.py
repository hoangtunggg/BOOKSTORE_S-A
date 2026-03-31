from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Electronic, ElectronicVariant
from .serializers import (
    ElectronicListSerializer, ElectronicDetailSerializer, ElectronicCreateSerializer,
    ElectronicVariantSerializer, ElectronicVariantCreateSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ElectronicListCreate(APIView):
    """List all electronics or create a new one"""
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        electronics = Electronic.objects.filter(is_active=True)
        
        # Filters
        sub_category = request.query_params.get('category')
        if sub_category:
            electronics = electronics.filter(sub_category=sub_category)
        
        brand = request.query_params.get('brand')
        if brand:
            electronics = electronics.filter(brand__iexact=brand)
        
        min_price = request.query_params.get('min_price')
        if min_price:
            electronics = electronics.filter(
                Q(sale_price__gte=min_price) | Q(sale_price__isnull=True, price__gte=min_price)
            )
        
        max_price = request.query_params.get('max_price')
        if max_price:
            electronics = electronics.filter(
                Q(sale_price__lte=max_price) | Q(sale_price__isnull=True, price__lte=max_price)
            )
        
        featured = request.query_params.get('featured')
        if featured and featured.lower() == 'true':
            electronics = electronics.filter(is_featured=True)
        
        search = request.query_params.get('search')
        if search:
            electronics = electronics.filter(
                Q(name__icontains=search) | Q(brand__icontains=search) | Q(model_number__icontains=search)
            )
        
        # Sorting
        sort = request.query_params.get('sort', '-created_at')
        sort_mapping = {
            'price_asc': 'price',
            'price_desc': '-price',
            'newest': '-created_at',
            'name': 'name',
        }
        sort_field = sort_mapping.get(sort, sort)
        electronics = electronics.order_by(sort_field)

        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(electronics, request)
        if page is not None:
            serializer = ElectronicListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ElectronicListSerializer(electronics, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ElectronicCreateSerializer(data=request.data)
        if serializer.is_valid():
            electronic = serializer.save()
            return Response(ElectronicDetailSerializer(electronic).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ElectronicDetail(APIView):
    """Retrieve, update or delete an electronic"""

    def get(self, request, pk):
        electronic = get_object_or_404(Electronic.objects.prefetch_related('variants'), pk=pk)
        serializer = ElectronicDetailSerializer(electronic)
        return Response(serializer.data)

    def patch(self, request, pk):
        electronic = get_object_or_404(Electronic, pk=pk)
        serializer = ElectronicCreateSerializer(electronic, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ElectronicDetailSerializer(electronic).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        electronic = get_object_or_404(Electronic, pk=pk)
        electronic.is_active = False
        electronic.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ElectronicReduceStock(APIView):
    """Reduce stock for an electronic"""

    def post(self, request, pk):
        try:
            electronic = Electronic.objects.get(pk=pk)
            quantity = int(request.data.get("quantity", 0))
            variant_id = request.data.get("variant_id")
            
            if variant_id:
                variant = ElectronicVariant.objects.get(pk=variant_id, electronic=electronic)
                if variant.stock < quantity:
                    return Response({
                        "error": f"Không đủ hàng cho '{variant.name}' (Cần: {quantity}, Hiện có: {variant.stock})"
                    }, status=400)
                variant.stock -= quantity
                variant.save()
                return Response({"success": True, "new_stock": variant.stock, "variant_id": variant_id})
            else:
                if electronic.stock < quantity:
                    return Response({
                        "error": f"Không đủ hàng cho '{electronic.name}' (Cần: {quantity}, Hiện có: {electronic.stock})"
                    }, status=400)
                electronic.stock -= quantity
                electronic.save()
                return Response({"success": True, "new_stock": electronic.stock})
                
        except Electronic.DoesNotExist:
            return Response({"error": "Sản phẩm không tồn tại"}, status=404)
        except ElectronicVariant.DoesNotExist:
            return Response({"error": "Variant không tồn tại"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ElectronicRestoreStock(APIView):
    """Restore stock for an electronic"""

    def post(self, request, pk):
        try:
            electronic = Electronic.objects.get(pk=pk)
            quantity = int(request.data.get("quantity", 0))
            variant_id = request.data.get("variant_id")
            
            if variant_id:
                variant = ElectronicVariant.objects.get(pk=variant_id, electronic=electronic)
                variant.stock += quantity
                variant.save()
                return Response({"success": True, "new_stock": variant.stock, "variant_id": variant_id})
            else:
                electronic.stock += quantity
                electronic.save()
                return Response({"success": True, "new_stock": electronic.stock})
                
        except Electronic.DoesNotExist:
            return Response({"error": "Sản phẩm không tồn tại"}, status=404)
        except ElectronicVariant.DoesNotExist:
            return Response({"error": "Variant không tồn tại"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ElectronicByCategory(APIView):
    """List electronics by category"""
    pagination_class = StandardResultsSetPagination

    def get(self, request, category):
        electronics = Electronic.objects.filter(sub_category=category, is_active=True)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(electronics, request)
        if page is not None:
            serializer = ElectronicListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ElectronicListSerializer(electronics, many=True)
        return Response(serializer.data)


class ElectronicByBrand(APIView):
    """List electronics by brand"""
    pagination_class = StandardResultsSetPagination

    def get(self, request, brand):
        electronics = Electronic.objects.filter(brand__iexact=brand, is_active=True)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(electronics, request)
        if page is not None:
            serializer = ElectronicListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ElectronicListSerializer(electronics, many=True)
        return Response(serializer.data)


class BrandList(APIView):
    """List all brands"""

    def get(self, request):
        brands = Electronic.objects.filter(is_active=True).values_list('brand', flat=True).distinct().order_by('brand')
        return Response(list(brands))


class CategoryList(APIView):
    """List all sub-categories"""

    def get(self, request):
        categories = [
            {'code': code, 'name': name}
            for code, name in Electronic.SUB_CATEGORIES
        ]
        return Response(categories)


# ==================== Variant Views ====================

class ElectronicVariantListCreate(APIView):
    """List variants for an electronic or create a new one"""

    def get(self, request, electronic_id):
        electronic = get_object_or_404(Electronic, pk=electronic_id)
        variants = electronic.variants.filter(is_active=True)
        serializer = ElectronicVariantSerializer(variants, many=True)
        return Response(serializer.data)

    def post(self, request, electronic_id):
        electronic = get_object_or_404(Electronic, pk=electronic_id)
        data = request.data.copy()
        data['electronic'] = electronic_id
        serializer = ElectronicVariantCreateSerializer(data=data)
        if serializer.is_valid():
            variant = serializer.save()
            return Response(ElectronicVariantSerializer(variant).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ElectronicVariantDetail(APIView):
    """Retrieve, update or delete a variant"""

    def get(self, request, sku):
        variant = get_object_or_404(ElectronicVariant.objects.select_related('electronic'), sku=sku)
        data = ElectronicVariantSerializer(variant).data
        data['electronic'] = ElectronicListSerializer(variant.electronic).data
        return Response(data)

    def patch(self, request, sku):
        variant = get_object_or_404(ElectronicVariant, sku=sku)
        serializer = ElectronicVariantCreateSerializer(variant, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ElectronicVariantSerializer(variant).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, sku):
        variant = get_object_or_404(ElectronicVariant, sku=sku)
        variant.is_active = False
        variant.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
