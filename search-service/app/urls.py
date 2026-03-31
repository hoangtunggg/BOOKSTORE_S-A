from django.urls import path
from .views import (
    ProductSearch,
    SearchSuggest,
    IndexProduct,
    BulkIndexProducts,
    DeleteProductIndex,
    RebuildIndex,
    IndexHealth,
)

urlpatterns = [
    # Search endpoints
    path('search/', ProductSearch.as_view(), name='product_search'),
    path('search/suggest/', SearchSuggest.as_view(), name='search_suggest'),
    
    # Index management endpoints (internal use)
    path('index/product/', IndexProduct.as_view(), name='index_product'),
    path('index/products/bulk/', BulkIndexProducts.as_view(), name='bulk_index'),
    path('index/product/<uuid:product_uuid>/', DeleteProductIndex.as_view(), name='delete_product_index'),
    path('index/rebuild/', RebuildIndex.as_view(), name='rebuild_index'),
    
    # Health check
    path('health/', IndexHealth.as_view(), name='health'),
]
