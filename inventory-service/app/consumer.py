"""
Inventory Service Consumer - Part of Saga Pattern

Listens for order_created events and handles stock reservations.
Publishes stock_reserved or stock_failed events.
"""
import pika
import json
import os
import sys
import django
from datetime import timedelta

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_service.settings')
django.setup()

from django.db import transaction
from django.utils import timezone
from app.models import ProductVariant, InventoryItem, StockReservation

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
RESERVATION_EXPIRY_MINUTES = int(os.environ.get('RESERVATION_EXPIRY_MINUTES', '30'))


def publish_event(queue_name, data):
    """Publish event to RabbitMQ queue"""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2)  # Persistent
        )
        connection.close()
        print(f"Published to {queue_name}: {data}")
    except Exception as e:
        print(f"Failed to publish to {queue_name}: {e}")


def reserve_stock_for_order(order_id, items):
    """
    Reserve stock for all items in an order.
    Returns (success, message, reserved_items)
    """
    reserved_items = []
    expires_at = timezone.now() + timedelta(minutes=RESERVATION_EXPIRY_MINUTES)
    
    try:
        with transaction.atomic():
            for item in items:
                variant_sku = item.get('variant_sku')
                quantity = item.get('quantity', 1)
                
                if not variant_sku:
                    # Skip items without variant_sku (old system book_id items)
                    continue
                
                # Get variant
                try:
                    variant = ProductVariant.objects.get(sku=variant_sku, is_active=True)
                except ProductVariant.DoesNotExist:
                    return False, f"Variant {variant_sku} not found or inactive", []
                
                # Find best warehouse with available stock
                inventory_items = InventoryItem.objects.filter(
                    variant=variant,
                    warehouse__is_active=True
                ).select_for_update().order_by('-warehouse__priority')
                
                remaining_qty = quantity
                for inv_item in inventory_items:
                    available = inv_item.available_quantity
                    if available <= 0:
                        continue
                    
                    reserve_qty = min(available, remaining_qty)
                    
                    # Create reservation
                    reservation, created = StockReservation.objects.get_or_create(
                        inventory_item=inv_item,
                        order_id=order_id,
                        defaults={
                            'quantity': reserve_qty,
                            'expires_at': expires_at,
                            'status': 'active'
                        }
                    )
                    
                    if not created:
                        # Already reserved for this order
                        reservation.quantity += reserve_qty
                        reservation.expires_at = expires_at
                        reservation.status = 'active'
                        reservation.save()
                    
                    # Update inventory
                    inv_item.reserved_quantity += reserve_qty
                    inv_item.save()
                    
                    reserved_items.append({
                        'variant_sku': variant_sku,
                        'warehouse_code': inv_item.warehouse.code,
                        'quantity': reserve_qty,
                        'reservation_id': reservation.id
                    })
                    
                    remaining_qty -= reserve_qty
                    if remaining_qty <= 0:
                        break
                
                if remaining_qty > 0:
                    # Not enough stock, rollback (transaction.atomic will handle)
                    raise Exception(f"Insufficient stock for {variant_sku}: need {quantity}, available {quantity - remaining_qty}")
            
            return True, "Stock reserved successfully", reserved_items
            
    except Exception as e:
        return False, str(e), []


def callback_order_created(ch, method, properties, body):
    """Handle order_created event - Reserve stock for items"""
    data = json.loads(body)
    order_id = data.get('order_id')
    items = data.get('items', [])
    
    print(f"Received order_created for order {order_id} with {len(items)} items")
    
    # Check if any items use new variant system
    has_variant_items = any(item.get('variant_sku') for item in items)
    
    if has_variant_items:
        # Reserve stock for variant items
        success, message, reserved_items = reserve_stock_for_order(order_id, items)
        
        if success:
            # Publish success - continue saga
            publish_event('stock_reserved_queue', {
                'order_id': order_id,
                'reserved_items': reserved_items,
                'message': message
            })
        else:
            # Publish failure - saga will compensate
            publish_event('stock_failed_queue', {
                'order_id': order_id,
                'reason': message
            })
    else:
        # No variant items, pass through (old system)
        # Payment service handles directly
        print(f"Order {order_id} has no variant items, passing through to old flow")
        publish_event('stock_reserved_queue', {
            'order_id': order_id,
            'reserved_items': [],
            'message': 'No variant items to reserve'
        })
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def callback_commit_reservation(ch, method, properties, body):
    """Handle stock commitment after successful payment"""
    data = json.loads(body)
    order_id = data.get('order_id')
    
    print(f"Committing reservations for order {order_id}")
    
    try:
        reservations = StockReservation.objects.filter(
            order_id=order_id,
            status='active'
        ).select_related('inventory_item')
        
        with transaction.atomic():
            for reservation in reservations:
                reservation.commit()
        
        publish_event('stock_committed_queue', {
            'order_id': order_id,
            'status': 'committed'
        })
        
    except Exception as e:
        print(f"Error committing reservation for order {order_id}: {e}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def callback_release_reservation(ch, method, properties, body):
    """Handle stock release for cancelled/failed orders"""
    data = json.loads(body)
    order_id = data.get('order_id')
    reason = data.get('reason', 'Order cancelled')
    
    print(f"Releasing reservations for order {order_id}: {reason}")
    
    try:
        reservations = StockReservation.objects.filter(
            order_id=order_id,
            status='active'
        ).select_related('inventory_item')
        
        with transaction.atomic():
            for reservation in reservations:
                reservation.release()
        
        publish_event('stock_released_queue', {
            'order_id': order_id,
            'status': 'released',
            'reason': reason
        })
        
    except Exception as e:
        print(f"Error releasing reservation for order {order_id}: {e}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def callback_payment_failed(ch, method, properties, body):
    """Handle payment failure - release reservations"""
    data = json.loads(body)
    order_id = data.get('order_id')
    reason = data.get('reason', 'Payment failed')
    
    print(f"Payment failed for order {order_id}, releasing stock")
    
    try:
        reservations = StockReservation.objects.filter(
            order_id=order_id,
            status='active'
        ).select_related('inventory_item')
        
        with transaction.atomic():
            for reservation in reservations:
                reservation.release()
        
        print(f"Released stock for order {order_id}")
        
    except Exception as e:
        print(f"Error releasing reservation for order {order_id}: {e}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consuming():
    """Start listening for events"""
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    
    # Listen for order created events
    channel.queue_declare(queue='order_created_queue', durable=True)
    channel.basic_consume(queue='order_created_queue', on_message_callback=callback_order_created)
    
    # Listen for commit/release requests
    channel.queue_declare(queue='commit_reservation_queue', durable=True)
    channel.basic_consume(queue='commit_reservation_queue', on_message_callback=callback_commit_reservation)
    
    channel.queue_declare(queue='release_reservation_queue', durable=True)
    channel.basic_consume(queue='release_reservation_queue', on_message_callback=callback_release_reservation)
    
    # Listen for payment failures (direct compensation)
    channel.queue_declare(queue='payment_failed_queue', durable=True)
    channel.basic_consume(queue='payment_failed_queue', on_message_callback=callback_payment_failed)
    
    print('Inventory Service is listening for events...')
    channel.start_consuming()


if __name__ == "__main__":
    start_consuming()
