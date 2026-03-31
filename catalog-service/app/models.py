from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """Category với hỗ trợ hierarchy (tree structure)"""
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Hierarchy
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='children'
    )
    level = models.PositiveIntegerField(default=0)  # 0 = root, 1 = child, etc.
    path = models.CharField(max_length=500, blank=True, db_index=True)  # Materialized path: "1/5/12"
    
    # Display
    image_url = models.URLField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    position = models.PositiveIntegerField(default=0)
    
    # Filtering
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    
    # Stats
    product_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ['position', 'name']
        indexes = [
            models.Index(fields=['parent']),
            models.Index(fields=['level', 'position']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-generate slug
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Calculate level
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0
        
        super().save(*args, **kwargs)
        
        # Update path after save to get ID
        self._update_path()

    def _update_path(self):
        if self.parent:
            new_path = f"{self.parent.path}/{self.pk}"
        else:
            new_path = str(self.pk)
        
        if self.path != new_path:
            Category.objects.filter(pk=self.pk).update(path=new_path)
            self.path = new_path
            # Update children paths
            for child in self.children.all():
                child._update_path()

    def get_ancestors(self):
        """Get all ancestors from root to parent"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    def get_descendants(self):
        """Get all descendants recursively"""
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants

    def get_all_product_ids(self, include_descendants=True):
        """Get all book_ids in this category and optionally descendants"""
        book_ids = list(BookCatalog.objects.filter(category=self).values_list('book_id', flat=True))
        product_uuids = list(ProductCatalog.objects.filter(category=self).values_list('product_uuid', flat=True))
        
        if include_descendants:
            for descendant in self.get_descendants():
                book_ids.extend(BookCatalog.objects.filter(category=descendant).values_list('book_id', flat=True))
                product_uuids.extend(ProductCatalog.objects.filter(category=descendant).values_list('product_uuid', flat=True))
        
        return {
            'book_ids': list(set(book_ids)),
            'product_uuids': [str(uuid) for uuid in set(product_uuids)]
        }


class CategoryProductType(models.Model):
    """Mapping category với product types được phép"""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='allowed_types')
    product_type_code = models.CharField(max_length=50)  # "book", "clothing", "electronics"
    
    class Meta:
        unique_together = ('category', 'product_type_code')

    def __str__(self):
        return f"{self.category.name} -> {self.product_type_code}"


class BookCatalog(models.Model):
    """Maps book_id from book-service to categories (backward compatible)."""
    book_id = models.IntegerField()
    category = models.ForeignKey(Category, related_name='books', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('book_id', 'category')

    def __str__(self):
        return f"Book#{self.book_id} -> {self.category.name}"


class ProductCatalog(models.Model):
    """Generic product-category mapping using product_uuid from Product Core Service"""
    product_uuid = models.UUIDField(db_index=True)
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('product_uuid', 'category')
        indexes = [
            models.Index(fields=['product_uuid']),
        ]

    def __str__(self):
        return f"Product {self.product_uuid} -> {self.category.name}"

    def save(self, *args, **kwargs):
        # Ensure only one primary category per product
        if self.is_primary:
            ProductCatalog.objects.filter(product_uuid=self.product_uuid, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
