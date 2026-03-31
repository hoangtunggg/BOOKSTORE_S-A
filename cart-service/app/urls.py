from django.urls import path
from .views import (
    CartCreate, AddCartItem, CartView, DeleteCartItem, ClearCart,
    UpdateCartItemQuantity, DeleteCartItemByProduct, CartItemDetail
)

urlpatterns = [
    # Cart
    path('carts/', CartCreate.as_view(), name='cart-create'),
    path('carts/<int:customer_id>/', CartView.as_view(), name='cart-view'),
    path('carts/<int:customer_id>/clear/', ClearCart.as_view(), name='cart-clear'),
    
    # Cart Items
    path('cart-items/', AddCartItem.as_view(), name='cart-item-add'),
    path('cart-items/<int:item_id>/', CartItemDetail.as_view(), name='cart-item-detail'),
    path('cart-items/<int:item_id>/quantity/', UpdateCartItemQuantity.as_view(), name='cart-item-quantity'),
    
    # Delete by book_id (backward compatible)
    path('cart-items/<int:cart_id>/<int:book_id>/', DeleteCartItem.as_view(), name='cart-item-delete-book'),
    
    # Delete by product_uuid (new unified approach)
    path('cart-items/<int:cart_id>/product/<uuid:product_uuid>/', DeleteCartItemByProduct.as_view(), name='cart-item-delete-product'),
]
