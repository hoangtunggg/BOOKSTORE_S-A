"""
Elasticsearch client and index management for Search Service
"""
from elasticsearch import Elasticsearch
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def get_es_client():
    """Get Elasticsearch client"""
    return Elasticsearch([settings.ELASTICSEARCH_URL])


PRODUCT_INDEX = "products"

PRODUCT_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "vietnamese": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "uuid": {"type": "keyword"},
            "name": {
                "type": "text",
                "analyzer": "vietnamese",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "suggest": {
                        "type": "completion",
                        "analyzer": "vietnamese"
                    }
                }
            },
            "description": {"type": "text", "analyzer": "vietnamese"},
            "slug": {"type": "keyword"},
            "product_type": {"type": "keyword"},
            "product_type_name": {"type": "keyword"},
            "categories": {"type": "keyword"},  # List of category IDs
            "category_names": {"type": "text", "analyzer": "vietnamese"},
            "category_paths": {"type": "keyword"},  # Materialized paths for hierarchy
            "base_price": {"type": "float"},
            "sale_price": {"type": "float"},
            "current_price": {"type": "float"},  # Computed: sale_price or base_price
            "attributes": {
                "type": "object",
                "enabled": True,
                "dynamic": True
            },
            "avg_rating": {"type": "float"},
            "review_count": {"type": "integer"},
            "sold_count": {"type": "integer"},
            "view_count": {"type": "integer"},
            "is_active": {"type": "boolean"},
            "is_featured": {"type": "boolean"},
            "images": {
                "type": "nested",
                "properties": {
                    "url": {"type": "keyword"},
                    "is_primary": {"type": "boolean"}
                }
            },
            "thumbnail": {"type": "keyword"},  # Primary image URL
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
            # For sorting/boosting
            "popularity_score": {"type": "float"}  # Computed score
        }
    }
}


def create_index():
    """Create the products index if it doesn't exist"""
    es = get_es_client()
    try:
        if not es.indices.exists(index=PRODUCT_INDEX):
            es.indices.create(index=PRODUCT_INDEX, body=PRODUCT_MAPPING)
            logger.info(f"Created index: {PRODUCT_INDEX}")
            return True
        else:
            logger.info(f"Index {PRODUCT_INDEX} already exists")
            return False
    except Exception as e:
        logger.error(f"Failed to create index: {e}")
        return False


def delete_index():
    """Delete the products index"""
    es = get_es_client()
    try:
        if es.indices.exists(index=PRODUCT_INDEX):
            es.indices.delete(index=PRODUCT_INDEX)
            logger.info(f"Deleted index: {PRODUCT_INDEX}")
            return True
    except Exception as e:
        logger.error(f"Failed to delete index: {e}")
    return False


def rebuild_index():
    """Delete and recreate the index"""
    delete_index()
    return create_index()


def index_product(product_data: dict):
    """Index a single product"""
    es = get_es_client()
    
    # Prepare document
    doc = prepare_product_document(product_data)
    
    try:
        es.index(
            index=PRODUCT_INDEX,
            id=doc["uuid"],
            document=doc
        )
        logger.info(f"Indexed product: {doc['uuid']}")
        return True
    except Exception as e:
        logger.error(f"Failed to index product {doc.get('uuid')}: {e}")
        return False


def bulk_index_products(products: list):
    """Bulk index products"""
    es = get_es_client()
    from elasticsearch.helpers import bulk
    
    actions = []
    for product in products:
        doc = prepare_product_document(product)
        actions.append({
            "_index": PRODUCT_INDEX,
            "_id": doc["uuid"],
            "_source": doc
        })
    
    try:
        success, failed = bulk(es, actions, stats_only=True)
        logger.info(f"Bulk indexed: {success} success, {failed} failed")
        return success, failed
    except Exception as e:
        logger.error(f"Bulk index failed: {e}")
        return 0, len(products)


def delete_product(product_uuid: str):
    """Delete a product from index"""
    es = get_es_client()
    try:
        es.delete(index=PRODUCT_INDEX, id=product_uuid)
        logger.info(f"Deleted product from index: {product_uuid}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete product {product_uuid}: {e}")
        return False


def prepare_product_document(product_data: dict) -> dict:
    """Prepare product data for indexing"""
    # Calculate current price
    base_price = float(product_data.get("base_price", 0))
    sale_price = product_data.get("sale_price")
    if sale_price:
        current_price = float(sale_price)
    else:
        current_price = base_price
    
    # Calculate popularity score
    avg_rating = float(product_data.get("avg_rating", 0))
    sold_count = int(product_data.get("sold_count", 0))
    review_count = int(product_data.get("review_count", 0))
    view_count = int(product_data.get("view_count", 0))
    
    popularity_score = (
        (avg_rating * 20) +  # 0-100 points for rating
        (min(sold_count / 10, 50)) +  # Up to 50 points for sales
        (min(review_count, 20)) +  # Up to 20 points for reviews
        (min(view_count / 100, 30))  # Up to 30 points for views
    )
    
    # Get primary image
    images = product_data.get("images", [])
    thumbnail = None
    for img in images:
        if img.get("is_primary"):
            thumbnail = img.get("url")
            break
    if not thumbnail and images:
        thumbnail = images[0].get("url")
    
    return {
        "uuid": str(product_data.get("uuid")),
        "name": product_data.get("name", ""),
        "description": product_data.get("description", ""),
        "slug": product_data.get("slug", ""),
        "product_type": product_data.get("product_type", {}).get("code") if isinstance(product_data.get("product_type"), dict) else product_data.get("product_type_code", ""),
        "product_type_name": product_data.get("product_type", {}).get("name") if isinstance(product_data.get("product_type"), dict) else "",
        "categories": product_data.get("categories", []),
        "category_names": product_data.get("category_names", []),
        "category_paths": product_data.get("category_paths", []),
        "base_price": base_price,
        "sale_price": float(sale_price) if sale_price else None,
        "current_price": current_price,
        "attributes": product_data.get("attributes", {}),
        "avg_rating": avg_rating,
        "review_count": review_count,
        "sold_count": sold_count,
        "view_count": view_count,
        "is_active": product_data.get("is_active", True),
        "is_featured": product_data.get("is_featured", False),
        "images": images,
        "thumbnail": thumbnail,
        "created_at": product_data.get("created_at"),
        "updated_at": product_data.get("updated_at"),
        "popularity_score": popularity_score
    }
