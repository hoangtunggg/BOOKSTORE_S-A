from django.urls import path
from .views import (
    WarehouseListCreate, WarehouseDetail,
    VariantListCreate, VariantDetail, VariantsByProduct,
    StockList, StockByVariant, StockCheck, StockAdjust, InitializeStock,
    ReserveStock, CommitReservation, ReleaseReservation, ReservationsByOrder,
    StockMovementList, MovementsByVariant,
    ExpireReservations
)

urlpatterns = [
    # Warehouses
    path('warehouses/', WarehouseListCreate.as_view(), name='warehouse-list'),
    path('warehouses/<str:code>/', WarehouseDetail.as_view(), name='warehouse-detail'),
    
    # Variants
    path('variants/', VariantListCreate.as_view(), name='variant-list'),
    path('variants/<str:sku>/', VariantDetail.as_view(), name='variant-detail'),
    path('variants/product/<uuid:product_uuid>/', VariantsByProduct.as_view(), name='variants-by-product'),
    
    # Stock
    path('stock/', StockList.as_view(), name='stock-list'),
    path('stock/variant/<str:sku>/', StockByVariant.as_view(), name='stock-by-variant'),
    path('stock/check/', StockCheck.as_view(), name='stock-check'),
    path('stock/adjust/', StockAdjust.as_view(), name='stock-adjust'),
    path('stock/initialize/', InitializeStock.as_view(), name='stock-initialize'),
    
    # Reservations
    path('stock/reserve/', ReserveStock.as_view(), name='reserve-stock'),
    path('stock/commit/<int:order_id>/', CommitReservation.as_view(), name='commit-reservation'),
    path('stock/release/<int:order_id>/', ReleaseReservation.as_view(), name='release-reservation'),
    path('reservations/order/<int:order_id>/', ReservationsByOrder.as_view(), name='reservations-by-order'),
    
    # Movements
    path('movements/', StockMovementList.as_view(), name='movement-list'),
    path('movements/variant/<str:sku>/', MovementsByVariant.as_view(), name='movements-by-variant'),
    
    # Maintenance
    path('reservations/expire/', ExpireReservations.as_view(), name='expire-reservations'),
]
