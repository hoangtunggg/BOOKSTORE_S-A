"""
Search Service Consumer - Listens for product events

Automatically updates the search index when products are
created, updated, or deleted in Product Core Service.
"""
import pika
import json
import os
import sys
import django

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'search_service.settings')
django.setup()

from app.elasticsearch_client import (
    index_product, delete_product, create_index
)

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')


def callback_product_created(ch, method, properties, body):
    """Handle product created event"""
    data = json.loads(body)
    print(f"Received product_created event: {data.get('uuid')}")
    
    if index_product(data):
        print(f"Indexed new product: {data.get('uuid')}")
    else:
        print(f"Failed to index product: {data.get('uuid')}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def callback_product_updated(ch, method, properties, body):
    """Handle product updated event"""
    data = json.loads(body)
    print(f"Received product_updated event: {data.get('uuid')}")
    
    if index_product(data):
        print(f"Re-indexed product: {data.get('uuid')}")
    else:
        print(f"Failed to re-index product: {data.get('uuid')}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def callback_product_deleted(ch, method, properties, body):
    """Handle product deleted event"""
    data = json.loads(body)
    product_uuid = data.get('uuid') or data.get('product_uuid')
    print(f"Received product_deleted event: {product_uuid}")
    
    if delete_product(product_uuid):
        print(f"Removed product from index: {product_uuid}")
    else:
        print(f"Failed to remove product from index: {product_uuid}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consuming():
    """Start listening for product events"""
    # Ensure index exists
    create_index()
    
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    
    # Product created events
    channel.queue_declare(queue='product_created_queue', durable=True)
    channel.basic_consume(queue='product_created_queue', on_message_callback=callback_product_created)
    
    # Product updated events
    channel.queue_declare(queue='product_updated_queue', durable=True)
    channel.basic_consume(queue='product_updated_queue', on_message_callback=callback_product_updated)
    
    # Product deleted events
    channel.queue_declare(queue='product_deleted_queue', durable=True)
    channel.basic_consume(queue='product_deleted_queue', on_message_callback=callback_product_deleted)
    
    print('Search Service is listening for product events...')
    channel.start_consuming()


if __name__ == "__main__":
    start_consuming()
