from django.urls import path
from .views import (
    ProductTypeListCreate, ProductTypeDetail, ProductTypeAttributes, AttributeDefinitionDetail,
    ProductListCreate, ProductDetail, ProductBySlug, ProductsByType,
    ProductAttributeList, ProductImageList, ProductImageDetail, ProductCategoryList,
    ProductSync, BulkProductSync, ProductUpdateStats, ProductByExternalId
)

urlpatterns = [
    # Product Types
    path('product-types/', ProductTypeListCreate.as_view(), name='product-type-list'),
    path('product-types/<str:code>/', ProductTypeDetail.as_view(), name='product-type-detail'),
    path('product-types/<str:code>/attributes/', ProductTypeAttributes.as_view(), name='product-type-attributes'),
    path('attributes/<int:pk>/', AttributeDefinitionDetail.as_view(), name='attribute-detail'),
    
    # Products
    path('products/', ProductListCreate.as_view(), name='product-list'),
    path('products/<uuid:uuid>/', ProductDetail.as_view(), name='product-detail'),
    path('products/slug/<slug:slug>/', ProductBySlug.as_view(), name='product-by-slug'),
    path('products/type/<str:type_code>/', ProductsByType.as_view(), name='products-by-type'),
    path('products/external/<str:type_code>/<int:external_id>/', ProductByExternalId.as_view(), name='product-by-external-id'),
    
    # Product Attributes
    path('products/<uuid:uuid>/attributes/', ProductAttributeList.as_view(), name='product-attributes'),
    
    # Product Images
    path('products/<uuid:uuid>/images/', ProductImageList.as_view(), name='product-images'),
    path('products/<uuid:uuid>/images/<int:image_id>/', ProductImageDetail.as_view(), name='product-image-detail'),
    
    # Product Categories
    path('products/<uuid:uuid>/categories/', ProductCategoryList.as_view(), name='product-categories'),
    
    # Sync endpoints (for internal use)
    path('products/sync/', ProductSync.as_view(), name='product-sync'),
    path('products/bulk-sync/', BulkProductSync.as_view(), name='bulk-product-sync'),
    path('products/<uuid:uuid>/stats/', ProductUpdateStats.as_view(), name='product-update-stats'),
]
