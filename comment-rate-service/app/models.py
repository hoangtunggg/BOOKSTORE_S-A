from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Review(models.Model):
    """
    Review/Rating cho sản phẩm.
    Hỗ trợ cả book_id (backward compatible) và product_uuid (unified approach).
    """
    customer_id = models.IntegerField(db_index=True)
    
    # Product reference - hỗ trợ cả hai cách
    book_id = models.IntegerField(null=True, blank=True, db_index=True)  # Backward compatible
    product_uuid = models.UUIDField(null=True, blank=True, db_index=True)  # New unified approach
    
    # Order reference để verify đã mua
    order_id = models.IntegerField(null=True, blank=True)
    order_item_id = models.IntegerField(null=True, blank=True)
    
    # Rating & Comment
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    
    # Review images
    images = models.JSONField(default=list, help_text='Danh sách URL hình ảnh review')
    
    # Helpful votes
    helpful_count = models.IntegerField(default=0)
    not_helpful_count = models.IntegerField(default=0)
    
    # Seller response
    seller_response = models.TextField(blank=True)
    seller_response_at = models.DateTimeField(null=True, blank=True)
    
    # Flags
    is_verified_purchase = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Một customer chỉ được review một sản phẩm một lần
        constraints = [
            models.UniqueConstraint(
                fields=['customer_id', 'book_id'],
                condition=models.Q(book_id__isnull=False),
                name='unique_customer_book_review'
            ),
            models.UniqueConstraint(
                fields=['customer_id', 'product_uuid'],
                condition=models.Q(product_uuid__isnull=False),
                name='unique_customer_product_review'
            ),
        ]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer_id']),
            models.Index(fields=['rating']),
            models.Index(fields=['is_verified_purchase']),
        ]

    def __str__(self):
        product_ref = self.product_uuid or f"Book#{self.book_id}"
        return f"Review by Customer#{self.customer_id} for {product_ref} - {self.rating}/5"


class ReviewHelpful(models.Model):
    """Tracking helpful votes để tránh vote nhiều lần"""
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='votes')
    customer_id = models.IntegerField()
    is_helpful = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('review', 'customer_id')

    def __str__(self):
        vote_type = "helpful" if self.is_helpful else "not helpful"
        return f"Customer#{self.customer_id} voted {vote_type} for Review#{self.review_id}"
