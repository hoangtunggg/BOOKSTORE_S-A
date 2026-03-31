from django.urls import path
from .views import (
    CategoryListCreate, CategoryDetail, CategoryBySlug, CategoryTree,
    CategoryChildren, CategoryAncestors, CategoryDescendants, CategoryAllowedTypes,
    BookCatalogListCreate, BookCatalogDelete,
    ProductCatalogListCreate, ProductCatalogDelete,
    CategoryProducts, UpdateProductCount
)

urlpatterns = [
    # Categories
    path('categories/', CategoryListCreate.as_view(), name='category-list'),
    path('categories/tree/', CategoryTree.as_view(), name='category-tree'),
    path('categories/<int:pk>/', CategoryDetail.as_view(), name='category-detail'),
    path('categories/slug/<slug:slug>/', CategoryBySlug.as_view(), name='category-by-slug'),
    path('categories/<int:pk>/children/', CategoryChildren.as_view(), name='category-children'),
    path('categories/<int:pk>/ancestors/', CategoryAncestors.as_view(), name='category-ancestors'),
    path('categories/<int:pk>/descendants/', CategoryDescendants.as_view(), name='category-descendants'),
    path('categories/<int:pk>/allowed-types/', CategoryAllowedTypes.as_view(), name='category-allowed-types'),
    path('categories/<int:pk>/products/', CategoryProducts.as_view(), name='category-products'),
    path('categories/<int:pk>/update-count/', UpdateProductCount.as_view(), name='update-product-count'),
    
    # Book Catalogs (backward compatible)
    path('book-catalogs/', BookCatalogListCreate.as_view(), name='book-catalog-list'),
    path('book-catalogs/<int:book_id>/<int:category_id>/', BookCatalogDelete.as_view(), name='book-catalog-delete'),
    
    # Product Catalogs (new unified approach)
    path('product-catalogs/', ProductCatalogListCreate.as_view(), name='product-catalog-list'),
    path('product-catalogs/<uuid:product_uuid>/<int:category_id>/', ProductCatalogDelete.as_view(), name='product-catalog-delete'),
]
