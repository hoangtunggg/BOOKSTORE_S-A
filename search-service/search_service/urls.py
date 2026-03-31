"""search_service URL Configuration"""
from django.urls import path, include

urlpatterns = [
    path('', include('app.urls')),
]
