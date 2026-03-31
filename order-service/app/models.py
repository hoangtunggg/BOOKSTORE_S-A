from django.db import models
import uuid


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Chờ xử lý'),
        ('confirmed', 'Đã xác nhận'),
        ('paid', 'Đã thanh toán'),
        ('shipping', 'Đang giao hàng'),
        ('delivered', 'Đã giao hàng'),
        ('cancelled', 'Đã hủy'),
    )
    PAYMENT_METHODS = (
        ('cod', 'Thanh toán khi nhận hàng (COD)'),
        ('bank_transfer', 'Chuyển khoản ngân hàng'),
        ('e_wallet', 'Ví điện tử'),
    )
    PAYMENT_STATUS_CHOICES = (
        ('unpaid', 'Chưa thanh toán'),
        ('paid', 'Đã thanh toán'),
        ('refunded', 'Đã hoàn tiền'),
    )

    # Order identification
    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    
    customer_id = models.IntegerField(db_index=True)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cod')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    
    # Shipping
    shipping_address = models.TextField()
    shipping_name = models.CharField(max_length=255, blank=True)
    shipping_phone = models.CharField(max_length=20, blank=True)
    tracking_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Notes
    customer_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer_id', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Order {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate unique order number
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    """
    Order item - hỗ trợ cả book_id (backward compatible) và product_uuid (unified).
    """
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    
    # Product reference - backward compatible
    book_id = models.IntegerField(null=True, blank=True)
    
    # Product reference - unified
    product_uuid = models.UUIDField(null=True, blank=True)
    variant_sku = models.CharField(max_length=100, null=True, blank=True)
    
    # Product snapshot (immutable record of what was ordered)
    product_name = models.CharField(max_length=255)
    product_type = models.CharField(max_length=50, blank=True)  # 'book', 'clothing', 'electronics'
    product_thumbnail = models.URLField(blank=True)
    
    # Quantity & Price
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Variant info snapshot
    variant_name = models.CharField(max_length=255, blank=True)
    variant_attributes = models.JSONField(default=dict)  # {"color": "black", "size": "M"}
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"

    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
