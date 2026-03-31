from django.db import models


class Electronic(models.Model):
    """
    Sản phẩm điện tử - mẫu cho product type mới.
    Service này quản lý chi tiết sản phẩm điện tử như điện thoại, laptop, tablet, phụ kiện.
    """
    SUB_CATEGORIES = [
        ('phone', 'Điện thoại'),
        ('laptop', 'Laptop'),
        ('tablet', 'Máy tính bảng'),
        ('smartwatch', 'Đồng hồ thông minh'),
        ('earphone', 'Tai nghe'),
        ('accessory', 'Phụ kiện'),
        ('camera', 'Máy ảnh'),
        ('gaming', 'Gaming'),
        ('home_appliance', 'Đồ gia dụng'),
    ]

    # Basic info
    name = models.CharField(max_length=255, db_index=True)
    brand = models.CharField(max_length=100, db_index=True)
    model_number = models.CharField(max_length=100)
    sub_category = models.CharField(max_length=50, choices=SUB_CATEGORIES)
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Inventory
    stock = models.IntegerField(default=0)
    
    # Warranty
    warranty_months = models.IntegerField(default=12)
    
    # Flexible specs stored as JSON
    specifications = models.JSONField(
        default=dict,
        help_text='Ví dụ: {"RAM": "8GB", "Storage": "256GB", "Screen": "6.1 inch", "Battery": "4000mAh"}'
    )
    
    # Description
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    
    # Images
    thumbnail = models.URLField(blank=True)
    images = models.JSONField(default=list, help_text='Danh sách URL hình ảnh')
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'electronics'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['brand']),
            models.Index(fields=['sub_category']),
            models.Index(fields=['is_active', 'is_featured']),
        ]

    def __str__(self):
        return f"{self.brand} {self.name}"

    @property
    def current_price(self):
        return self.sale_price if self.sale_price else self.price

    @property
    def discount_percent(self):
        if self.sale_price and self.price > 0:
            return round((1 - self.sale_price / self.price) * 100)
        return 0


class ElectronicVariant(models.Model):
    """
    Biến thể của sản phẩm điện tử (màu sắc, dung lượng, v.v.)
    """
    electronic = models.ForeignKey(
        Electronic, 
        on_delete=models.CASCADE, 
        related_name='variants'
    )
    name = models.CharField(max_length=255, help_text='Ví dụ: "iPhone 15 Pro - 256GB - Titan Đen"')
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Variant attributes
    color = models.CharField(max_length=50, blank=True)
    storage = models.CharField(max_length=50, blank=True)
    ram = models.CharField(max_length=50, blank=True)
    
    # Pricing modifier
    price_modifier = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Stock
    stock = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'electronic_variants'

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def final_price(self):
        return self.electronic.current_price + self.price_modifier
