import uuid
from django.db import models
from django.utils.text import slugify


class ProductType(models.Model):
    """
    Định nghĩa loại sản phẩm: book, clothing, electronics, etc.
    Mỗi loại sản phẩm có thể có service riêng để quản lý chi tiết.
    """
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    service_url = models.URLField(blank=True, help_text="URL của service chuyên biệt quản lý loại sản phẩm này")
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_types'
        ordering = ['name']

    def __str__(self):
        return self.name


class AttributeDefinition(models.Model):
    """
    Định nghĩa các thuộc tính có thể có cho mỗi loại sản phẩm.
    Ví dụ: Book có author, publisher; Clothing có size, color, material.
    """
    DATA_TYPE_CHOICES = [
        ('string', 'String'),
        ('number', 'Number'),
        ('decimal', 'Decimal'),
        ('boolean', 'Boolean'),
        ('list', 'List'),
        ('date', 'Date'),
    ]

    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.CASCADE,
        related_name='attribute_definitions'
    )
    name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, default='string')
    is_required = models.BooleanField(default=False)
    is_filterable = models.BooleanField(default=True, help_text="Có thể filter/search theo thuộc tính này không")
    is_variant = models.BooleanField(default=False, help_text="Là variant attribute không (size, color)")
    options = models.JSONField(null=True, blank=True, help_text='Cho select options: ["S", "M", "L", "XL"]')
    default_value = models.JSONField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attribute_definitions'
        unique_together = ('product_type', 'name')
        ordering = ['product_type', 'position', 'name']

    def __str__(self):
        return f"{self.product_type.code}.{self.name}"


class Product(models.Model):
    """
    Sản phẩm chung - aggregation từ các service chuyên biệt.
    Đây là central product catalog để hỗ trợ search, filter, và display.
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.PROTECT,
        related_name='products'
    )
    external_id = models.IntegerField(help_text="ID trong service gốc (book_id, clothe_id)")
    
    # Basic info
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    
    # Pricing
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    
    # SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Stats (denormalized for performance)
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.IntegerField(default=0)
    sold_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        unique_together = ('product_type', 'external_id')
        indexes = [
            models.Index(fields=['product_type', 'is_active']),
            models.Index(fields=['avg_rating']),
            models.Index(fields=['sold_count']),
            models.Index(fields=['created_at']),
            models.Index(fields=['base_price']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def current_price(self):
        """Trả về giá hiện tại (sale_price nếu có, ngược lại base_price)"""
        return self.sale_price if self.sale_price else self.base_price

    @property
    def discount_percent(self):
        """Tính phần trăm giảm giá"""
        if self.sale_price and self.base_price > 0:
            return round((1 - self.sale_price / self.base_price) * 100)
        return 0


class ProductAttribute(models.Model):
    """
    Lưu giá trị thuộc tính của từng sản phẩm.
    Sử dụng EAV pattern để linh hoạt với các thuộc tính khác nhau.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='attributes'
    )
    attribute = models.ForeignKey(
        AttributeDefinition,
        on_delete=models.CASCADE
    )
    value = models.JSONField(help_text='Flexible storage: "J.K. Rowling", ["S", "M"], 16, true')

    class Meta:
        db_table = 'product_attributes'
        unique_together = ('product', 'attribute')
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['attribute']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.attribute.display_name}: {self.value}"


class ProductImage(models.Model):
    """Hình ảnh sản phẩm"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    url = models.URLField()
    alt_text = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_images'
        ordering = ['position']

    def __str__(self):
        return f"{self.product.name} - Image {self.position}"

    def save(self, *args, **kwargs):
        # Ensure only one primary image per product
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductCategory(models.Model):
    """
    Many-to-many giữa Product và Category.
    Category được quản lý bởi Catalog Service, ở đây chỉ lưu reference.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    category_id = models.IntegerField(help_text="Reference to Category in Catalog Service")
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_categories'
        unique_together = ('product', 'category_id')
        indexes = [
            models.Index(fields=['category_id']),
        ]

    def __str__(self):
        return f"{self.product.name} - Category {self.category_id}"

    def save(self, *args, **kwargs):
        # Ensure only one primary category per product
        if self.is_primary:
            ProductCategory.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
