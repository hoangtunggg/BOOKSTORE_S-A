from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Review, ReviewHelpful
from .serializers import (
    ReviewSerializer, ReviewListSerializer, ReviewDetailSerializer, ReviewCreateSerializer,
    SellerResponseSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ReviewListCreate(APIView):
    """List all reviews or create a new one"""
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        reviews = Review.objects.filter(is_visible=True)
        
        # Filters
        customer_id = request.query_params.get('customer_id')
        if customer_id:
            reviews = reviews.filter(customer_id=customer_id)
        
        verified_only = request.query_params.get('verified')
        if verified_only and verified_only.lower() == 'true':
            reviews = reviews.filter(is_verified_purchase=True)
        
        min_rating = request.query_params.get('min_rating')
        if min_rating:
            reviews = reviews.filter(rating__gte=min_rating)
        
        with_images = request.query_params.get('with_images')
        if with_images and with_images.lower() == 'true':
            reviews = reviews.exclude(images=[])

        # Sorting
        sort = request.query_params.get('sort', '-created_at')
        sort_mapping = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'highest': '-rating',
            'lowest': 'rating',
            'helpful': '-helpful_count',
        }
        sort_field = sort_mapping.get(sort, sort)
        reviews = reviews.order_by(sort_field)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(reviews, request)
        if page is not None:
            serializer = ReviewListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        return Response(ReviewListSerializer(reviews, many=True).data)

    def post(self, request):
        serializer = ReviewCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Check if order exists and is delivered (if order_id provided)
            order_id = serializer.validated_data.get('order_id')
            if order_id:
                # In production, verify with order service
                serializer.validated_data['is_verified_purchase'] = True
            
            review = serializer.save()
            return Response(ReviewDetailSerializer(review).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReviewsByBook(APIView):
    """Get reviews for a book (backward compatible)"""
    pagination_class = StandardResultsSetPagination

    def get(self, request, book_id):
        reviews = Review.objects.filter(book_id=book_id, is_visible=True)
        
        # Stats
        stats = reviews.aggregate(
            avg=Avg('rating'),
            total=Count('id'),
            verified=Count('id', filter=Q(is_verified_purchase=True))
        )
        
        # Rating distribution
        distribution = {}
        for i in range(1, 6):
            distribution[str(i)] = reviews.filter(rating=i).count()
        
        # Sorting
        sort = request.query_params.get('sort', '-created_at')
        sort_mapping = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'highest': '-rating',
            'lowest': 'rating',
            'helpful': '-helpful_count',
        }
        sort_field = sort_mapping.get(sort, sort)
        reviews = reviews.order_by(sort_field)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(reviews, request)
        
        response_data = {
            'book_id': book_id,
            'average_rating': round(stats['avg'], 1) if stats['avg'] else 0,
            'total_reviews': stats['total'],
            'verified_reviews': stats['verified'],
            'rating_distribution': distribution,
        }
        
        if page is not None:
            response_data['reviews'] = ReviewListSerializer(page, many=True).data
            return paginator.get_paginated_response(response_data)
        
        response_data['reviews'] = ReviewListSerializer(reviews, many=True).data
        return Response(response_data)


class ReviewsByProduct(APIView):
    """Get reviews for a product by UUID (new unified approach)"""
    pagination_class = StandardResultsSetPagination

    def get(self, request, product_uuid):
        reviews = Review.objects.filter(product_uuid=product_uuid, is_visible=True)
        
        # Stats
        stats = reviews.aggregate(
            avg=Avg('rating'),
            total=Count('id'),
            verified=Count('id', filter=Q(is_verified_purchase=True))
        )
        
        # Rating distribution
        distribution = {}
        for i in range(1, 6):
            distribution[str(i)] = reviews.filter(rating=i).count()
        
        # Sorting
        sort = request.query_params.get('sort', '-created_at')
        sort_mapping = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'highest': '-rating',
            'lowest': 'rating',
            'helpful': '-helpful_count',
        }
        sort_field = sort_mapping.get(sort, sort)
        reviews = reviews.order_by(sort_field)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(reviews, request)
        
        response_data = {
            'product_uuid': str(product_uuid),
            'average_rating': round(stats['avg'], 1) if stats['avg'] else 0,
            'total_reviews': stats['total'],
            'verified_reviews': stats['verified'],
            'rating_distribution': distribution,
        }
        
        if page is not None:
            response_data['reviews'] = ReviewListSerializer(page, many=True).data
            return paginator.get_paginated_response(response_data)
        
        response_data['reviews'] = ReviewListSerializer(reviews, many=True).data
        return Response(response_data)


class ReviewDetail(APIView):
    """Retrieve, update or delete a review"""

    def get(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        return Response(ReviewDetailSerializer(review).data)

    def patch(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        
        # Only allow updating certain fields
        allowed_fields = ['rating', 'title', 'comment', 'images']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = ReviewSerializer(review, data=update_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ReviewDetailSerializer(review).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        review.is_visible = False  # Soft delete
        review.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReviewsByCustomer(APIView):
    """Get all reviews by a customer"""
    pagination_class = StandardResultsSetPagination

    def get(self, request, customer_id):
        reviews = Review.objects.filter(customer_id=customer_id, is_visible=True)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(reviews, request)
        if page is not None:
            serializer = ReviewListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        return Response(ReviewListSerializer(reviews, many=True).data)


class MarkReviewHelpful(APIView):
    """Mark a review as helpful or not helpful"""

    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        customer_id = request.data.get('customer_id')
        is_helpful = request.data.get('is_helpful', True)
        
        if not customer_id:
            return Response({"error": "customer_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already voted
        existing = ReviewHelpful.objects.filter(review=review, customer_id=customer_id).first()
        
        if existing:
            # Update existing vote
            if existing.is_helpful != is_helpful:
                # Changed vote
                if existing.is_helpful:
                    review.helpful_count -= 1
                    review.not_helpful_count += 1
                else:
                    review.not_helpful_count -= 1
                    review.helpful_count += 1
                existing.is_helpful = is_helpful
                existing.save()
                review.save()
            return Response({
                'helpful_count': review.helpful_count,
                'not_helpful_count': review.not_helpful_count
            })
        
        # New vote
        ReviewHelpful.objects.create(review=review, customer_id=customer_id, is_helpful=is_helpful)
        if is_helpful:
            review.helpful_count += 1
        else:
            review.not_helpful_count += 1
        review.save()
        
        return Response({
            'helpful_count': review.helpful_count,
            'not_helpful_count': review.not_helpful_count
        })


class SellerResponse(APIView):
    """Add seller response to a review"""

    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        serializer = SellerResponseSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        review.seller_response = serializer.validated_data['response']
        review.seller_response_at = timezone.now()
        review.save()
        
        return Response(ReviewDetailSerializer(review).data)


class ProductReviewStats(APIView):
    """Get review statistics for a product (for Product Core Service to update stats)"""

    def get(self, request, product_uuid):
        reviews = Review.objects.filter(product_uuid=product_uuid, is_visible=True)
        
        stats = reviews.aggregate(
            avg=Avg('rating'),
            total=Count('id')
        )
        
        return Response({
            'product_uuid': str(product_uuid),
            'average_rating': round(stats['avg'], 2) if stats['avg'] else 0,
            'review_count': stats['total']
        })


class BookReviewStats(APIView):
    """Get review statistics for a book (backward compatible)"""

    def get(self, request, book_id):
        reviews = Review.objects.filter(book_id=book_id, is_visible=True)
        
        stats = reviews.aggregate(
            avg=Avg('rating'),
            total=Count('id')
        )
        
        return Response({
            'book_id': book_id,
            'average_rating': round(stats['avg'], 2) if stats['avg'] else 0,
            'review_count': stats['total']
        })
