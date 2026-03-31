#!/usr/bin/env python3
"""
Data Migration Script: Migrate existing books/clothes to Product Core Service

This script syncs product data from specialized services (book-service, clothe-service)
to the product-core-service for unified product management.

Usage:
    python migrate_to_product_core.py --service book
    python migrate_to_product_core.py --service clothe
    python migrate_to_product_core.py --service all

Environment Variables:
    BOOK_SERVICE_URL: URL of book service (default: http://localhost:8002)
    CLOTHE_SERVICE_URL: URL of clothe service (default: http://localhost:8013)
    PRODUCT_CORE_SERVICE_URL: URL of product core service (default: http://localhost:8014)
"""

import requests
import argparse
import sys
import os
from datetime import datetime


# Service URLs
BOOK_SERVICE_URL = os.environ.get('BOOK_SERVICE_URL', 'http://localhost:8002')
CLOTHE_SERVICE_URL = os.environ.get('CLOTHE_SERVICE_URL', 'http://localhost:8013')
PRODUCT_CORE_SERVICE_URL = os.environ.get('PRODUCT_CORE_SERVICE_URL', 'http://localhost:8014')
INVENTORY_SERVICE_URL = os.environ.get('INVENTORY_SERVICE_URL', 'http://localhost:8015')


def ensure_product_type(type_code, type_name, service_url):
    """Ensure a product type exists in Product Core Service"""
    try:
        # Check if type exists
        r = requests.get(f"{PRODUCT_CORE_SERVICE_URL}/product-types/{type_code}/", timeout=5)
        if r.status_code == 200:
            print(f"  Product type '{type_code}' already exists")
            return r.json()
        
        # Create type
        data = {
            "code": type_code,
            "name": type_name,
            "service_url": service_url,
            "is_active": True
        }
        r = requests.post(f"{PRODUCT_CORE_SERVICE_URL}/product-types/", json=data, timeout=5)
        if r.status_code in (200, 201):
            print(f"  Created product type: {type_code}")
            return r.json()
        else:
            print(f"  Failed to create product type: {r.text}")
            return None
    except Exception as e:
        print(f"  Error creating product type: {e}")
        return None


def ensure_attribute_definitions(type_code, attributes):
    """Ensure attribute definitions exist for a product type"""
    for attr in attributes:
        try:
            data = {
                "name": attr["name"],
                "display_name": attr["display_name"],
                "data_type": attr.get("data_type", "string"),
                "is_required": attr.get("is_required", False),
                "is_filterable": attr.get("is_filterable", True),
                "is_variant": attr.get("is_variant", False),
                "options": attr.get("options")
            }
            r = requests.post(
                f"{PRODUCT_CORE_SERVICE_URL}/product-types/{type_code}/attributes/",
                json=data, timeout=5
            )
            if r.status_code in (200, 201):
                print(f"    Created attribute: {attr['name']}")
            elif r.status_code == 400 and 'unique' in r.text.lower():
                print(f"    Attribute '{attr['name']}' already exists")
        except Exception as e:
            print(f"    Error creating attribute {attr['name']}: {e}")


def migrate_books():
    """Migrate books from book-service to product-core-service"""
    print("\n=== Migrating Books ===")
    
    # Ensure product type exists
    product_type = ensure_product_type("book", "Sách", f"{BOOK_SERVICE_URL}")
    if not product_type:
        print("Failed to create book product type")
        return False
    
    # Create attribute definitions for books
    book_attributes = [
        {"name": "author", "display_name": "Tác giả", "data_type": "string", "is_required": True, "is_filterable": True},
        {"name": "publisher", "display_name": "Nhà xuất bản", "data_type": "string", "is_filterable": True},
        {"name": "isbn", "display_name": "ISBN", "data_type": "string"},
        {"name": "pages", "display_name": "Số trang", "data_type": "number"},
        {"name": "language", "display_name": "Ngôn ngữ", "data_type": "string", "is_filterable": True},
        {"name": "format", "display_name": "Định dạng", "data_type": "string", "options": ["Bìa mềm", "Bìa cứng", "E-book"]},
    ]
    ensure_attribute_definitions("book", book_attributes)
    
    # Fetch all books
    try:
        r = requests.get(f"{BOOK_SERVICE_URL}/books/", timeout=10)
        if r.status_code != 200:
            print(f"Failed to fetch books: {r.status_code}")
            return False
        books = r.json()
    except Exception as e:
        print(f"Error fetching books: {e}")
        return False
    
    print(f"Found {len(books)} books to migrate")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for book in books:
        try:
            # Prepare product data
            product_data = {
                "product_type_code": "book",
                "external_id": book["id"],
                "name": book.get("title") or book.get("name", f"Book {book['id']}"),
                "description": book.get("description", ""),
                "base_price": float(book.get("price", 0)),
                "is_active": True,
                "attributes": {
                    "author": book.get("author", "Unknown"),
                },
                "images": []
            }
            
            # Add thumbnail if available
            if book.get("thumbnail"):
                product_data["images"].append({
                    "url": book["thumbnail"],
                    "is_primary": True,
                    "alt_text": product_data["name"]
                })
            
            # Sync to product core
            r = requests.post(
                f"{PRODUCT_CORE_SERVICE_URL}/products/sync/",
                json=product_data, timeout=10
            )
            
            if r.status_code in (200, 201):
                success_count += 1
                product = r.json()
                print(f"  ✓ Migrated: {product_data['name'][:50]}... -> UUID: {product.get('uuid', 'N/A')}")
                
                # Create inventory item with current stock
                stock = book.get("stock", 0)
                if stock > 0:
                    try:
                        variant_data = {
                            "product_uuid": product.get("uuid"),
                            "sku": f"BOOK-{book['id']}",
                            "name": product_data["name"],
                            "attributes": {},
                            "is_active": True
                        }
                        rv = requests.post(f"{INVENTORY_SERVICE_URL}/variants/", json=variant_data, timeout=5)
                        if rv.status_code in (200, 201):
                            print(f"    Created variant SKU: BOOK-{book['id']}")
                    except Exception as ve:
                        print(f"    Note: Could not create variant: {ve}")
                        
            elif r.status_code == 400 and 'already exists' in r.text.lower():
                skip_count += 1
                print(f"  - Skipped (exists): {product_data['name'][:50]}...")
            else:
                error_count += 1
                print(f"  ✗ Failed: {product_data['name'][:50]}... - {r.text[:100]}")
                
        except Exception as e:
            error_count += 1
            print(f"  ✗ Error migrating book {book.get('id')}: {e}")
    
    print(f"\nBooks migration complete: {success_count} migrated, {skip_count} skipped, {error_count} errors")
    return error_count == 0


def migrate_clothes():
    """Migrate clothes from clothe-service to product-core-service"""
    print("\n=== Migrating Clothes ===")
    
    # Ensure product type exists
    product_type = ensure_product_type("clothing", "Quần áo", f"{CLOTHE_SERVICE_URL}")
    if not product_type:
        print("Failed to create clothing product type")
        return False
    
    # Create attribute definitions for clothing
    clothing_attributes = [
        {"name": "material", "display_name": "Chất liệu", "data_type": "string", "is_filterable": True},
        {"name": "size", "display_name": "Kích cỡ", "data_type": "list", "is_variant": True, "options": ["XS", "S", "M", "L", "XL", "XXL"]},
        {"name": "color", "display_name": "Màu sắc", "data_type": "string", "is_variant": True, "is_filterable": True},
        {"name": "brand", "display_name": "Thương hiệu", "data_type": "string", "is_filterable": True},
        {"name": "gender", "display_name": "Giới tính", "data_type": "string", "options": ["Nam", "Nữ", "Unisex"], "is_filterable": True},
    ]
    ensure_attribute_definitions("clothing", clothing_attributes)
    
    # Fetch all clothes
    try:
        r = requests.get(f"{CLOTHE_SERVICE_URL}/clothes/", timeout=10)
        if r.status_code != 200:
            print(f"Failed to fetch clothes: {r.status_code}")
            return False
        clothes = r.json()
    except Exception as e:
        print(f"Error fetching clothes: {e}")
        return False
    
    print(f"Found {len(clothes)} clothes to migrate")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for clothe in clothes:
        try:
            # Prepare product data
            product_data = {
                "product_type_code": "clothing",
                "external_id": clothe["id"],
                "name": clothe.get("name", f"Clothe {clothe['id']}"),
                "description": clothe.get("description", ""),
                "base_price": float(clothe.get("price", 0)),
                "is_active": True,
                "attributes": {
                    "material": clothe.get("material", ""),
                },
                "images": []
            }
            
            # Add thumbnail if available
            if clothe.get("thumbnail"):
                product_data["images"].append({
                    "url": clothe["thumbnail"],
                    "is_primary": True,
                    "alt_text": product_data["name"]
                })
            
            # Sync to product core
            r = requests.post(
                f"{PRODUCT_CORE_SERVICE_URL}/products/sync/",
                json=product_data, timeout=10
            )
            
            if r.status_code in (200, 201):
                success_count += 1
                product = r.json()
                print(f"  ✓ Migrated: {product_data['name'][:50]}... -> UUID: {product.get('uuid', 'N/A')}")
                
                # Create inventory item with current stock
                stock = clothe.get("stock", 0)
                if stock > 0:
                    try:
                        variant_data = {
                            "product_uuid": product.get("uuid"),
                            "sku": f"CLOTH-{clothe['id']}",
                            "name": product_data["name"],
                            "attributes": {},
                            "is_active": True
                        }
                        rv = requests.post(f"{INVENTORY_SERVICE_URL}/variants/", json=variant_data, timeout=5)
                        if rv.status_code in (200, 201):
                            print(f"    Created variant SKU: CLOTH-{clothe['id']}")
                    except Exception as ve:
                        print(f"    Note: Could not create variant: {ve}")
                        
            elif r.status_code == 400 and 'already exists' in r.text.lower():
                skip_count += 1
                print(f"  - Skipped (exists): {product_data['name'][:50]}...")
            else:
                error_count += 1
                print(f"  ✗ Failed: {product_data['name'][:50]}... - {r.text[:100]}")
                
        except Exception as e:
            error_count += 1
            print(f"  ✗ Error migrating clothe {clothe.get('id')}: {e}")
    
    print(f"\nClothes migration complete: {success_count} migrated, {skip_count} skipped, {error_count} errors")
    return error_count == 0


def check_services():
    """Check if required services are available"""
    services = {
        "Product Core": PRODUCT_CORE_SERVICE_URL,
        "Inventory": INVENTORY_SERVICE_URL,
        "Book": BOOK_SERVICE_URL,
        "Clothe": CLOTHE_SERVICE_URL,
    }
    
    print("Checking services...")
    all_ok = True
    for name, url in services.items():
        try:
            r = requests.get(url, timeout=3)
            status = "✓ OK" if r.status_code < 500 else f"✗ Error ({r.status_code})"
        except Exception as e:
            status = f"✗ Unreachable ({e})"
            all_ok = False
        print(f"  {name}: {url} - {status}")
    
    return all_ok


def main():
    parser = argparse.ArgumentParser(description='Migrate products to Product Core Service')
    parser.add_argument(
        '--service', 
        choices=['book', 'clothe', 'all'], 
        default='all',
        help='Which service to migrate from (default: all)'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Only check service availability'
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("Product Migration to Product Core Service")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 60)
    
    if not check_services():
        print("\n⚠ Some services are not available. Continue? (y/n)")
        if input().lower() != 'y':
            sys.exit(1)
    
    if args.check:
        sys.exit(0)
    
    success = True
    
    if args.service in ('book', 'all'):
        if not migrate_books():
            success = False
    
    if args.service in ('clothe', 'all'):
        if not migrate_clothes():
            success = False
    
    print("\n" + "=" * 60)
    print(f"Migration completed at: {datetime.now().isoformat()}")
    print("Status:", "SUCCESS" if success else "COMPLETED WITH ERRORS")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
