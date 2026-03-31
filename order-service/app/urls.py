from django.urls import path
from .views import OrderListCreate, OrderDetail, OrderByNumber

urlpatterns = [
    path('orders/', OrderListCreate.as_view()),
    path('orders/customer/<int:customer_id>/', OrderListCreate.as_view()),
    path('orders/<int:pk>/', OrderDetail.as_view()),
    path('orders/number/<str:order_number>/', OrderByNumber.as_view()),
]
