from django.db import models


class Cart(models.Model):
    customer_id = models.IntegerField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for Customer#{self.customer_id}"


class CartItem(models.Model):
    """
    Cart item - hỗ trợ cả book_id (backward compatible) và product_uuid (unified).
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    
    # Product reference - backward compatible
    book_id = models.IntegerField(null=True, blank=True, db_index=True)
    
    # Product reference - unified approach
    product_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    variant_sku = models.CharField(max_length=100, null=True, blank=True)
    
    # Quantity
    quantity = models.IntegerField()
    
    # Snapshot at time of adding (để đảm bảo giá không đổi trong cart)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    product_name = models.CharField(max_length=255, blank=True)
    product_type = models.CharField(max_length=50, blank=True)  # 'book', 'clothing', 'electronics'
    thumbnail_url = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Đảm bảo không duplicate items
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'book_id'],
                condition=models.Q(book_id__isnull=False),
                name='unique_cart_book'
            ),
            models.UniqueConstraint(
                fields=['cart', 'product_uuid', 'variant_sku'],
                condition=models.Q(product_uuid__isnull=False),
                name='unique_cart_product_variant'
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        product_ref = self.product_uuid or f"Book#{self.book_id}"
        return f"CartItem: {self.quantity}x {product_ref}"

    @property
    def total_price(self):
        if self.unit_price:
            return self.unit_price * self.quantity
        return None
