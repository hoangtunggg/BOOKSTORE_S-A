from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
import requests
import logging

from .elasticsearch_client import (
    get_es_client, PRODUCT_INDEX,
    index_product, bulk_index_products, delete_product,
    create_index, rebuild_index
)

logger = logging.getLogger(__name__)


class SearchPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductSearch(APIView):
    """
    Full-text search for products with faceted filtering
    
    Query params:
    - q: Search query (searches name, description)
    - type: Product type codes (comma-separated)
    - category: Category IDs (comma-separated)
    - price_min: Minimum price
    - price_max: Maximum price
    - rating_min: Minimum rating
    - in_stock: Only show in-stock items
    - featured: Only featured items
    - sort: Sorting option (relevance, price_asc, price_desc, rating, newest, bestseller)
    - page: Page number
    - page_size: Results per page
    """
    
    def get(self, request):
        es = get_es_client()
        
        # Parse query params
        q = request.query_params.get('q', '')
        product_types = request.query_params.get('type', '').split(',') if request.query_params.get('type') else []
        categories = request.query_params.get('category', '').split(',') if request.query_params.get('category') else []
        price_min = request.query_params.get('price_min')
        price_max = request.query_params.get('price_max')
        rating_min = request.query_params.get('rating_min')
        featured = request.query_params.get('featured', '').lower() == 'true'
        sort_by = request.query_params.get('sort', 'relevance')
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        
        # Build query
        must_queries = []
        filter_queries = [{"term": {"is_active": True}}]
        
        # Full-text search
        if q:
            must_queries.append({
                "multi_match": {
                    "query": q,
                    "fields": ["name^3", "description", "category_names", "attributes.*"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })
        
        # Product type filter
        if product_types and product_types[0]:
            filter_queries.append({"terms": {"product_type": product_types}})
        
        # Category filter (including subcategories via path)
        if categories and categories[0]:
            category_queries = []
            for cat_id in categories:
                category_queries.append({"term": {"categories": cat_id}})
                category_queries.append({"wildcard": {"category_paths": f"*/{cat_id}/*"}})
                category_queries.append({"wildcard": {"category_paths": f"{cat_id}/*"}})
            filter_queries.append({"bool": {"should": category_queries, "minimum_should_match": 1}})
        
        # Price filter
        if price_min or price_max:
            price_range = {}
            if price_min:
                price_range["gte"] = float(price_min)
            if price_max:
                price_range["lte"] = float(price_max)
            filter_queries.append({"range": {"current_price": price_range}})
        
        # Rating filter
        if rating_min:
            filter_queries.append({"range": {"avg_rating": {"gte": float(rating_min)}}})
        
        # Featured filter
        if featured:
            filter_queries.append({"term": {"is_featured": True}})
        
        # Build final query
        if must_queries:
            query = {
                "bool": {
                    "must": must_queries,
                    "filter": filter_queries
                }
            }
        else:
            query = {
                "bool": {
                    "filter": filter_queries
                }
            }
        
        # Sorting
        sort_options = {
            "relevance": ["_score", {"popularity_score": "desc"}],
            "price_asc": [{"current_price": "asc"}],
            "price_desc": [{"current_price": "desc"}],
            "rating": [{"avg_rating": "desc"}, {"review_count": "desc"}],
            "newest": [{"created_at": "desc"}],
            "bestseller": [{"sold_count": "desc"}],
            "popularity": [{"popularity_score": "desc"}]
        }
        sort = sort_options.get(sort_by, sort_options["relevance"])
        
        # Execute search
        try:
            result = es.search(
                index=PRODUCT_INDEX,
                query=query,
                sort=sort,
                from_=(page - 1) * page_size,
                size=page_size,
                aggs={
                    "product_types": {
                        "terms": {"field": "product_type", "size": 20}
                    },
                    "price_range": {
                        "stats": {"field": "current_price"}
                    },
                    "avg_ratings": {
                        "histogram": {"field": "avg_rating", "interval": 1}
                    }
                }
            )
            
            # Format response
            hits = result["hits"]["hits"]
            total = result["hits"]["total"]["value"]
            
            products = []
            for hit in hits:
                product = hit["_source"]
                product["_score"] = hit.get("_score")
                products.append(product)
            
            # Facets
            facets = {
                "product_types": [
                    {"code": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in result["aggregations"]["product_types"]["buckets"]
                ],
                "price_range": {
                    "min": result["aggregations"]["price_range"].get("min", 0),
                    "max": result["aggregations"]["price_range"].get("max", 0),
                    "avg": result["aggregations"]["price_range"].get("avg", 0),
                },
                "ratings": [
                    {"rating": int(bucket["key"]), "count": bucket["doc_count"]}
                    for bucket in result["aggregations"]["avg_ratings"]["buckets"]
                ]
            }
            
            return Response({
                "results": products,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "facets": facets
            })
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchSuggest(APIView):
    """
    Autocomplete suggestions
    
    Query params:
    - q: Partial query
    - size: Number of suggestions (default 5)
    """
    
    def get(self, request):
        es = get_es_client()
        q = request.query_params.get('q', '')
        size = min(int(request.query_params.get('size', 5)), 10)
        
        if not q or len(q) < 2:
            return Response({"suggestions": []})
        
        try:
            result = es.search(
                index=PRODUCT_INDEX,
                suggest={
                    "product_suggest": {
                        "prefix": q,
                        "completion": {
                            "field": "name.suggest",
                            "size": size,
                            "skip_duplicates": True,
                            "fuzzy": {
                                "fuzziness": 1
                            }
                        }
                    }
                }
            )
            
            suggestions = []
            for option in result["suggest"]["product_suggest"][0]["options"]:
                suggestions.append({
                    "text": option["text"],
                    "uuid": option["_source"]["uuid"],
                    "product_type": option["_source"].get("product_type", "")
                })
            
            return Response({"suggestions": suggestions})
            
        except Exception as e:
            logger.error(f"Suggest failed: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IndexProduct(APIView):
    """Index a single product"""
    
    def post(self, request):
        product_data = request.data
        
        if not product_data.get("uuid"):
            return Response({"error": "uuid is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if index_product(product_data):
            return Response({"status": "indexed", "uuid": product_data["uuid"]})
        else:
            return Response({"error": "Failed to index"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkIndexProducts(APIView):
    """Bulk index products"""
    
    def post(self, request):
        products = request.data.get("products", [])
        
        if not products:
            return Response({"error": "No products provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        success, failed = bulk_index_products(products)
        return Response({
            "status": "completed",
            "success": success,
            "failed": failed
        })


class DeleteProductIndex(APIView):
    """Delete a product from index"""
    
    def delete(self, request, product_uuid):
        if delete_product(str(product_uuid)):
            return Response({"status": "deleted", "uuid": str(product_uuid)})
        else:
            return Response({"error": "Failed to delete"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RebuildIndex(APIView):
    """Rebuild the entire index from Product Core Service"""
    
    def post(self, request):
        # Recreate index
        if not rebuild_index():
            return Response({"error": "Failed to recreate index"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Fetch all products from Product Core Service
        try:
            all_products = []
            page = 1
            while True:
                r = requests.get(
                    f"{settings.PRODUCT_CORE_SERVICE_URL}/products/",
                    params={"page": page, "page_size": 100},
                    timeout=30
                )
                if r.status_code != 200:
                    break
                
                data = r.json()
                products = data.get("results", data) if isinstance(data, dict) else data
                
                if not products:
                    break
                
                all_products.extend(products)
                
                # Check if there are more pages
                if isinstance(data, dict) and data.get("next"):
                    page += 1
                else:
                    break
            
            # Bulk index
            success, failed = bulk_index_products(all_products)
            
            return Response({
                "status": "completed",
                "total_products": len(all_products),
                "success": success,
                "failed": failed
            })
            
        except Exception as e:
            logger.error(f"Rebuild index failed: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IndexHealth(APIView):
    """Check Elasticsearch and index health"""
    
    def get(self, request):
        try:
            es = get_es_client()
            
            # Cluster health
            cluster_health = es.cluster.health()
            
            # Index stats
            index_exists = es.indices.exists(index=PRODUCT_INDEX)
            index_stats = None
            if index_exists:
                stats = es.indices.stats(index=PRODUCT_INDEX)
                index_stats = {
                    "docs_count": stats["_all"]["primaries"]["docs"]["count"],
                    "store_size": stats["_all"]["primaries"]["store"]["size_in_bytes"],
                }
            
            return Response({
                "elasticsearch": "connected",
                "cluster_status": cluster_health["status"],
                "index_exists": index_exists,
                "index_stats": index_stats
            })
            
        except Exception as e:
            return Response({
                "elasticsearch": "error",
                "error": str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
