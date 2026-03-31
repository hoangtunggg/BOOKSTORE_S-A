import uuid
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings


class Warehouse(models.Model):
    """Kho hàng"""
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text="Ưu tiên xuất hàng (số lớn = ưu tiên cao)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'warehouses'
        ordering = ['-priority', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class ProductVariant(models.Model):
    """
    Biến thể sản phẩm (SKU).
    Mỗi product có thể có nhiều variants (size, color combinations).
    """
    product_uuid = models.UUIDField(db_index=True, help_text="Reference to Product in Product Core Service")
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255, help_text='Ví dụ: "iPhone 15 - 128GB - Đen"')
    attributes = models.JSONField(default=dict, help_text='Ví dụ: {"color": "black", "size": "128GB"}')
    barcode = models.CharField(max_length=100, blank=True, db_index=True)
    price_modifier = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Thay đổi giá so với base price (có thể âm hoặc dương)"
    )
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Gram")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_variants'
        indexes = [
            models.Index(fields=['product_uuid']),
            models.Index(fields=['sku']),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def get_total_stock(self):
        """Get total stock across all warehouses"""
        return sum(item.available_quantity for item in self.inventory_items.all())


class InventoryItem(models.Model):
    """Tồn kho theo variant và warehouse"""
    variant = models.ForeignKey(
        ProductVariant, 
        on_delete=models.CASCADE,
        related_name='inventory_items'
    )
    warehouse = models.ForeignKey(
        Warehouse, 
        on_delete=models.CASCADE,
        related_name='inventory_items'
    )
    quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0, help_text="Đang giữ cho đơn hàng pending")
    low_stock_threshold = models.IntegerField(default=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory_items'
        unique_together = ('variant', 'warehouse')
        indexes = [
            models.Index(fields=['variant', 'warehouse']),
        ]

    def __str__(self):
        return f"{self.variant.sku} @ {self.warehouse.code}: {self.available_quantity}/{self.quantity}"

    @property
    def available_quantity(self):
        """Số lượng có thể bán (đã trừ reserved)"""
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def is_low_stock(self):
        return self.available_quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        return self.available_quantity <= 0


class StockMovement(models.Model):
    """Lịch sử xuất/nhập kho"""
    MOVEMENT_TYPES = [
        ('in', 'Nhập kho'),
        ('out', 'Xuất kho'),
        ('adjustment', 'Điều chỉnh'),
        ('transfer_out', 'Chuyển kho (xuất)'),
        ('transfer_in', 'Chuyển kho (nhập)'),
        ('reserve', 'Đặt trước'),
        ('release', 'Hủy đặt trước'),
        ('commit', 'Xác nhận đặt trước'),
    ]

    REFERENCE_TYPES = [
        ('order', 'Đơn hàng'),
        ('return', 'Trả hàng'),
        ('purchase', 'Nhập hàng'),
        ('transfer', 'Chuyển kho'),
        ('manual', 'Điều chỉnh thủ công'),
        ('system', 'Hệ thống'),
    ]

    inventory_item = models.ForeignKey(
        InventoryItem, 
        on_delete=models.CASCADE,
        related_name='movements'
    )
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Dương cho nhập, âm cho xuất")
    quantity_before = models.IntegerField(help_text="Số lượng trước khi thay đổi")
    quantity_after = models.IntegerField(help_text="Số lượng sau khi thay đổi")
    reference_type = models.CharField(max_length=50, choices=REFERENCE_TYPES, blank=True)
    reference_id = models.CharField(max_length=100, blank=True, help_text="Order ID, etc.")
    notes = models.TextField(blank=True)
    created_by = models.CharField(max_length=100, blank=True, help_text="User/service who made the change")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['inventory_item', 'created_at']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]

    def __str__(self):
        return f"{self.movement_type}: {self.quantity} @ {self.inventory_item}"


class StockReservation(models.Model):
    """
    Đặt trước hàng cho đơn hàng pending.
    Reservation sẽ auto-release nếu đơn không confirm trong thời gian quy định.
    """
    STATUSES = [
        ('active', 'Đang giữ'),
        ('committed', 'Đã xác nhận'),
        ('released', 'Đã hủy'),
        ('expired', 'Hết hạn'),
    ]

    reservation_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    inventory_item = models.ForeignKey(
        InventoryItem, 
        on_delete=models.CASCADE,
        related_name='reservations'
    )
    order_id = models.IntegerField(db_index=True)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUSES, default='active')
    expires_at = models.DateTimeField()
    committed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_reservations'
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self):
        return f"Reservation {self.reservation_id} for Order #{self.order_id}: {self.quantity}x {self.inventory_item.variant.sku}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            minutes = getattr(settings, 'RESERVATION_EXPIRY_MINUTES', 30)
            self.expires_at = timezone.now() + timedelta(minutes=minutes)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.status == 'active' and timezone.now() > self.expires_at

    def commit(self):
        """Xác nhận reservation - chuyển từ reserved sang committed"""
        if self.status != 'active':
            return False
        
        self.status = 'committed'
        self.committed_at = timezone.now()
        
        # Actually reduce the stock
        item = self.inventory_item
        item.reserved_quantity -= self.quantity
        item.quantity -= self.quantity
        item.save()
        
        # Log movement
        StockMovement.objects.create(
            inventory_item=item,
            movement_type='commit',
            quantity=-self.quantity,
            quantity_before=item.quantity + self.quantity,
            quantity_after=item.quantity,
            reference_type='order',
            reference_id=str(self.order_id),
            notes=f"Committed reservation {self.reservation_id}"
        )
        
        self.save()
        return True

    def release(self, reason=''):
        """Hủy reservation - trả lại reserved quantity"""
        if self.status != 'active':
            return False
        
        self.status = 'released'
        self.released_at = timezone.now()
        
        # Release the reserved quantity
        item = self.inventory_item
        item.reserved_quantity -= self.quantity
        item.save()
        
        # Log movement
        StockMovement.objects.create(
            inventory_item=item,
            movement_type='release',
            quantity=self.quantity,
            quantity_before=item.reserved_quantity + self.quantity,
            quantity_after=item.reserved_quantity,
            reference_type='order',
            reference_id=str(self.order_id),
            notes=f"Released reservation {self.reservation_id}. {reason}"
        )
        
        self.save()
        return True
