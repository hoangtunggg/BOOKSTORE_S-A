from rest_framework import serializers
from .models import Review, ReviewHelpful


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['helpful_count', 'not_helpful_count', 'seller_response', 
                          'seller_response_at', 'is_featured', 'created_at', 'updated_at']


class ReviewListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing"""
    class Meta:
        model = Review
        fields = ['id', 'customer_id', 'book_id', 'product_uuid', 'rating', 'title', 
                  'comment', 'images', 'helpful_count', 'is_verified_purchase', 
                  'is_featured', 'seller_response', 'created_at']


class ReviewDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail view"""
    class Meta:
        model = Review
        fields = ['id', 'customer_id', 'book_id', 'product_uuid', 'order_id', 'order_item_id',
                  'rating', 'title', 'comment', 'images',
                  'helpful_count', 'not_helpful_count',
                  'seller_response', 'seller_response_at',
                  'is_verified_purchase', 'is_featured', 'is_visible',
                  'created_at', 'updated_at']


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reviews"""
    class Meta:
        model = Review
        fields = ['customer_id', 'book_id', 'product_uuid', 'order_id', 'order_item_id',
                  'rating', 'title', 'comment', 'images']

    def validate(self, data):
        # Must have either book_id or product_uuid
        if not data.get('book_id') and not data.get('product_uuid'):
            raise serializers.ValidationError("Either book_id or product_uuid is required")
        return data


class SellerResponseSerializer(serializers.Serializer):
    """Serializer for seller response"""
    response = serializers.CharField()


class ReviewHelpfulSerializer(serializers.Serializer):
    """Serializer for marking review as helpful/not helpful"""
    is_helpful = serializers.BooleanField()


class ReviewStatsSerializer(serializers.Serializer):
    """Serializer for review statistics"""
    total_reviews = serializers.IntegerField()
    average_rating = serializers.FloatField()
    verified_count = serializers.IntegerField()
    rating_distribution = serializers.DictField()
