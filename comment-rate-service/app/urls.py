from django.urls import path
from .views import (
    ReviewListCreate, ReviewsByBook, ReviewsByProduct, ReviewDetail,
    ReviewsByCustomer, MarkReviewHelpful, SellerResponse,
    ProductReviewStats, BookReviewStats
)

urlpatterns = [
    # Reviews CRUD
    path('reviews/', ReviewListCreate.as_view(), name='review-list'),
    path('reviews/<int:pk>/', ReviewDetail.as_view(), name='review-detail'),
    
    # Reviews by reference (backward compatible)
    path('reviews/book/<int:book_id>/', ReviewsByBook.as_view(), name='reviews-by-book'),
    
    # Reviews by product UUID (new unified approach)
    path('reviews/product/<uuid:product_uuid>/', ReviewsByProduct.as_view(), name='reviews-by-product'),
    
    # Reviews by customer
    path('reviews/customer/<int:customer_id>/', ReviewsByCustomer.as_view(), name='reviews-by-customer'),
    
    # Actions
    path('reviews/<int:pk>/helpful/', MarkReviewHelpful.as_view(), name='mark-review-helpful'),
    path('reviews/<int:pk>/seller-response/', SellerResponse.as_view(), name='seller-response'),
    
    # Stats endpoints (for other services)
    path('stats/product/<uuid:product_uuid>/', ProductReviewStats.as_view(), name='product-review-stats'),
    path('stats/book/<int:book_id>/', BookReviewStats.as_view(), name='book-review-stats'),
]
