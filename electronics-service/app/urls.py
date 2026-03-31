from django.urls import path
from .views import (
    ElectronicListCreate, ElectronicDetail, ElectronicReduceStock, ElectronicRestoreStock,
    ElectronicByCategory, ElectronicByBrand, BrandList, CategoryList,
    ElectronicVariantListCreate, ElectronicVariantDetail
)

urlpatterns = [
    # Electronics
    path('electronics/', ElectronicListCreate.as_view(), name='electronic-list'),
    path('electronics/<int:pk>/', ElectronicDetail.as_view(), name='electronic-detail'),
    path('electronics/<int:pk>/reduce-stock/', ElectronicReduceStock.as_view(), name='electronic-reduce-stock'),
    path('electronics/<int:pk>/restore-stock/', ElectronicRestoreStock.as_view(), name='electronic-restore-stock'),
    
    # Filters
    path('electronics/category/<str:category>/', ElectronicByCategory.as_view(), name='electronics-by-category'),
    path('electronics/brand/<str:brand>/', ElectronicByBrand.as_view(), name='electronics-by-brand'),
    
    # Meta
    path('brands/', BrandList.as_view(), name='brand-list'),
    path('categories/', CategoryList.as_view(), name='category-list'),
    
    # Variants
    path('electronics/<int:electronic_id>/variants/', ElectronicVariantListCreate.as_view(), name='variant-list'),
    path('variants/<str:sku>/', ElectronicVariantDetail.as_view(), name='variant-detail'),
]
