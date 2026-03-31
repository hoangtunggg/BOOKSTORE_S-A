from django.urls import path
from .views import (
    home, book_list, customer_list, view_cart,
    admin_order_list, admin_order_detail,
    admin_staff_list, admin_manager_list, admin_catalog_list,
    admin_payment_list, admin_shipment_list, admin_review_list,
    store_home, store_login, store_register, store_logout,
    store_profile,
    store_cart, store_add_to_cart, store_remove_from_cart,
    store_book_detail, store_checkout,
    store_orders, store_order_detail, store_cancel_order,
    store_add_review,
    store_payment_simulate, store_confirm_receipt,
    api_secure_echo,
    admin_clothe_list, store_clothes, store_clothe_detail,
    # New API views
    api_products, api_product_detail, api_product_types, api_products_by_type,
    api_variants, api_variant_detail, api_variants_by_product,
    api_stock, api_stock_check, api_warehouses,
    api_electronics, api_electronic_detail,
    api_categories, api_category_tree, api_category_products,
    # New store views
    store_products, store_product_detail,
    store_electronics, store_electronic_detail,
    # Search API
    api_search, api_search_suggest,
)

urlpatterns = [
    # Admin
    path('', home, name='home'),
    path('books/', book_list, name='book_list'),
    path('admin/clothes/', admin_clothe_list, name='admin_clothe_list'),
    path('customers/', customer_list, name='customer_list'),
    path('cart/<int:customer_id>/', view_cart, name='view_cart'),
    path('orders/', admin_order_list, name='admin_order_list'),
    path('orders/<int:order_id>/', admin_order_detail, name='admin_order_detail'),
    path('staff/', admin_staff_list, name='admin_staff_list'),
    path('managers/', admin_manager_list, name='admin_manager_list'),
    path('catalog/', admin_catalog_list, name='admin_catalog_list'),
    path('payments/', admin_payment_list, name='admin_payment_list'),
    path('shipments/', admin_shipment_list, name='admin_shipment_list'),
    path('reviews/', admin_review_list, name='admin_review_list'),
    
    # Storefront
    path('store/', store_home, name='store_home'),
    path('clothes/', store_clothes, name='store_clothes'),
    path('store/clothes/', store_clothes, name='store_clothes'),
    path('store/clothes/<int:clothe_id>/', store_clothe_detail, name='store_clothe_detail'),
    path('store/login/', store_login, name='store_login'),
    path('store/register/', store_register, name='store_register'),
    path('store/logout/', store_logout, name='store_logout'),
    path('store/profile/', store_profile, name='store_profile'),
    path('store/cart/', store_cart, name='store_cart'),
    path('store/add-to-cart/', store_add_to_cart, name='store_add_to_cart'),
    path('store/remove-from-cart/<int:book_id>/', store_remove_from_cart, name='store_remove_from_cart'),
    path('store/book/<int:book_id>/', store_book_detail, name='store_book_detail'),
    path('store/checkout/', store_checkout, name='store_checkout'),
    path('store/orders/', store_orders, name='store_orders'),
    path('store/orders/<int:order_id>/', store_order_detail, name='store_order_detail'),
    path('store/orders/<int:order_id>/cancel/', store_cancel_order, name='store_cancel_order'),
    path('store/review/<int:book_id>/', store_add_review, name='store_add_review'),
    path('store/orders/<int:order_id>/pay/', store_payment_simulate, name='store_payment_simulate'),
    path('store/orders/<int:order_id>/confirm/', store_confirm_receipt, name='store_confirm_receipt'),
    
    # New store pages
    path('store/products/', store_products, name='store_products'),
    path('store/products/<uuid:product_uuid>/', store_product_detail, name='store_product_detail'),
    path('store/electronics/', store_electronics, name='store_electronics'),
    path('store/electronics/<int:electronic_id>/', store_electronic_detail, name='store_electronic_detail'),
    
    # API endpoints
    path('api/secure-echo/', api_secure_echo, name='api_secure_echo'),
    
    # Product Core APIs
    path('api/products/', api_products, name='api_products'),
    path('api/products/<uuid:product_uuid>/', api_product_detail, name='api_product_detail'),
    path('api/product-types/', api_product_types, name='api_product_types'),
    path('api/products/type/<str:type_code>/', api_products_by_type, name='api_products_by_type'),
    
    # Inventory APIs
    path('api/variants/', api_variants, name='api_variants'),
    path('api/variants/<str:sku>/', api_variant_detail, name='api_variant_detail'),
    path('api/variants/product/<uuid:product_uuid>/', api_variants_by_product, name='api_variants_by_product'),
    path('api/stock/', api_stock, name='api_stock'),
    path('api/stock/check/', api_stock_check, name='api_stock_check'),
    path('api/warehouses/', api_warehouses, name='api_warehouses'),
    
    # Electronics APIs
    path('api/electronics/', api_electronics, name='api_electronics'),
    path('api/electronics/<int:electronic_id>/', api_electronic_detail, name='api_electronic_detail'),
    
    # Category APIs
    path('api/categories/', api_categories, name='api_categories'),
    path('api/categories/tree/', api_category_tree, name='api_category_tree'),
    path('api/categories/<int:category_id>/products/', api_category_products, name='api_category_products'),
    
    # Search APIs
    path('api/search/', api_search, name='api_search'),
    path('api/search/suggest/', api_search_suggest, name='api_search_suggest'),
]
