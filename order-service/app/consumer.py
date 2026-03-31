import pika
import json
import os
import sys
import django
import requests

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'order_service.settings')
django.setup()

from app.models import Order, OrderItem
from django.utils import timezone

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
BOOK_SERVICE_URL = os.environ.get('BOOK_SERVICE_URL', 'http://book-service:8000')
CLOTHE_SERVICE_URL = os.environ.get('CLOTHE_SERVICE_URL', 'http://clothe-service:8000')
INVENTORY_SERVICE_URL = os.environ.get('INVENTORY_SERVICE_URL', 'http://inventory-service:8000')


def restore_stock_for_order(order):
    """
    Compensation logic: Restore stock when order is cancelled.
    Supports both old (book_id) and new (product_uuid/variant_sku) approaches.
    """
    for item in order.items.all():
        try:
            # New approach: Release inventory reservation
            if item.variant_sku:
                requests.post(
                    f"{INVENTORY_SERVICE_URL}/stock/release/{order.id}/",
                    json={"reason": "Order cancelled"},
                    timeout=5
                )
                print(f"Released inventory reservation for order {order.id}")
            
            # Old approach: Restore stock via book/clothe service
            elif item.book_id:
                if item.book_id > 1000000:
                    # Clothe
                    real_id = item.book_id - 1000000
                    requests.post(
                        f"{CLOTHE_SERVICE_URL}/clothes/{real_id}/restore-stock/",
                        json={"quantity": item.quantity},
                        timeout=3
                    )
                    print(f"Restored stock for clothe {real_id}, quantity {item.quantity}")
                else:
                    # Book
                    requests.post(
                        f"{BOOK_SERVICE_URL}/books/{item.book_id}/restore-stock/",
                        json={"quantity": item.quantity},
                        timeout=3
                    )
                    print(f"Restored stock for book {item.book_id}, quantity {item.quantity}")
                    
        except Exception as e:
            print(f"Failed to restore stock for item {item.id}: {e}")


def callback_success(ch, method, properties, body):
    """Handle successful saga completion"""
    data = json.loads(body)
    order_id = data.get('order_id')
    try:
        order = Order.objects.get(id=order_id)
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save()
        print(f"Order {order_id} confirmed by Saga success")
        
        # Commit inventory reservations (if using new approach)
        try:
            requests.post(
                f"{INVENTORY_SERVICE_URL}/stock/commit/{order_id}/",
                timeout=5
            )
            print(f"Committed inventory for order {order_id}")
        except Exception as e:
            print(f"Note: Could not commit inventory (may be using old approach): {e}")
            
    except Order.DoesNotExist:
        print(f"Order {order_id} not found")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def callback_failed(ch, method, properties, body):
    """Handle saga failure - perform compensation"""
    data = json.loads(body)
    order_id = data.get('order_id')
    reason = data.get('reason', 'Unknown reason')
    
    try:
        order = Order.objects.get(id=order_id)
        if order.status != 'cancelled':
            order.status = 'cancelled'
            order.cancelled_at = timezone.now()
            order.admin_note = f"Cancelled by saga: {reason}"
            order.save()
            print(f"Order {order_id} cancelled due to Saga failure: {reason}")
            
            # Compensation: Restore stock / Release reservations
            restore_stock_for_order(order)
                    
    except Order.DoesNotExist:
        print(f"Order {order_id} not found for cancellation")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def callback_stock_reserved(ch, method, properties, body):
    """Handle stock reservation success - continue to payment"""
    data = json.loads(body)
    order_id = data.get('order_id')
    print(f"Stock reserved for order {order_id}, proceeding with payment")
    # Payment service is already listening to order_created_queue
    # This callback is for logging/tracking purposes
    ch.basic_ack(delivery_tag=method.delivery_tag)


def callback_stock_failed(ch, method, properties, body):
    """Handle stock reservation failure"""
    data = json.loads(body)
    order_id = data.get('order_id')
    reason = data.get('reason', 'Insufficient stock')
    
    try:
        order = Order.objects.get(id=order_id)
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.admin_note = f"Stock reservation failed: {reason}"
        order.save()
        print(f"Order {order_id} cancelled due to stock failure: {reason}")
    except Order.DoesNotExist:
        print(f"Order {order_id} not found")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consuming():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    
    # Listen for saga success
    channel.queue_declare(queue='shipping_reserved_queue', durable=True)
    channel.basic_consume(queue='shipping_reserved_queue', on_message_callback=callback_success)
    
    # Listen for saga failures
    channel.queue_declare(queue='payment_failed_queue', durable=True)
    channel.basic_consume(queue='payment_failed_queue', on_message_callback=callback_failed)
    
    channel.queue_declare(queue='shipping_failed_queue', durable=True)
    channel.basic_consume(queue='shipping_failed_queue', on_message_callback=callback_failed)
    
    # Listen for inventory events (new saga flow)
    channel.queue_declare(queue='stock_reserved_queue', durable=True)
    channel.basic_consume(queue='stock_reserved_queue', on_message_callback=callback_stock_reserved)
    
    channel.queue_declare(queue='stock_failed_queue', durable=True)
    channel.basic_consume(queue='stock_failed_queue', on_message_callback=callback_stock_failed)
    
    print('Order service is waiting for Saga results...')
    channel.start_consuming()

if __name__ == "__main__":
    start_consuming()
