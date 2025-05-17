import os
import threading
import logging
import time
import uuid
from queue import Queue, Empty
from datetime import datetime, timedelta

from .. import crud, schemas
from ..database import SessionLocal
from ..utils.logging import log_delivery_attempt

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("threaded-worker")

# Retry intervals in seconds
RETRY_INTERVALS = [10, 30, 60, 300, 900]
MAX_ATTEMPTS = 5

# Create task queue
task_queue = Queue()

class ThreadedWorker:
    def __init__(self):
        self.worker_thread = None
        self.running = False
        self.scheduled_tasks = {}  # For storing scheduled retries
        
    def worker_loop(self):
        """The background worker process loop"""
        self.running = True
        logger.info("Starting threaded worker")
        
        while self.running:
            try:
                # Process scheduled tasks that are due
                current_time = time.time()
                tasks_to_run = []
                
                for task_id, (scheduled_time, task) in list(self.scheduled_tasks.items()):
                    if current_time >= scheduled_time:
                        tasks_to_run.append((task_id, task))
                
                # Run due tasks and remove them from scheduled_tasks
                for task_id, task in tasks_to_run:
                    self.scheduled_tasks.pop(task_id, None)
                    self.process_task(task)
                
                # Process new tasks from queue with a timeout
                try:
                    task = task_queue.get(timeout=1)
                    self.process_task(task)
                    task_queue.task_done()
                except Empty:
                    pass  # No new tasks, continue to next loop
                    
            except Exception as e:
                logger.error(f"Error in worker loop: {str(e)}")
                time.sleep(1)  # Pause briefly before continuing
    
    def process_task(self, task):
        """Process a delivery task"""
        delivery_id = task.get("delivery_id")
        attempt = task.get("attempt", 1)
        
        logger.info(f"Processing delivery {delivery_id}, attempt {attempt}")
        
        db = SessionLocal()
        try:
            # Get delivery details
            delivery = crud.get_delivery(db, delivery_id=uuid.UUID(delivery_id))
            if not delivery:
                logger.error(f"Delivery {delivery_id} not found")
                return
            
            # Get subscription
            subscription = crud.get_subscription(db, subscription_id=delivery.subscription_id)
            if not subscription:
                logger.error(f"Subscription {delivery.subscription_id} not found")
                return
            
            # Make the HTTP request
            import requests
            import json
            
            try:
                headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-Delivery-ID": str(delivery.id),
                    "X-Webhook-Subscription-ID": str(subscription.id)
                }
                
                if subscription.secret:
                    from ..utils.security import generate_signature
                    headers["X-Webhook-Signature"] = generate_signature(
                        subscription.secret, 
                        json.dumps(delivery.payload)
                    )
                
                response = requests.post(
                    subscription.target_url,
                    json=delivery.payload,
                    headers=headers,
                    timeout=10  # 10 seconds timeout
                )
                
                # Log the attempt
                success = 200 <= response.status_code < 300
                attempt_data = schemas.DeliveryAttemptCreate(
                    delivery_id=delivery.id,
                    subscription_id=subscription.id,
                    attempt_number=attempt,
                    status_code=response.status_code,
                    success=success,
                    error=None if success else response.text[:255]
                )
                crud.create_delivery_attempt(db, attempt_data)
                
                # Log to console/file
                log_delivery_attempt(
                    delivery_id=delivery.id,
                    subscription_id=subscription.id,
                    attempt_number=attempt,
                    status_code=response.status_code,
                    success=success,
                    error=None if success else response.text
                )
                
                # Update delivery status if successful or max attempts reached
                if success:
                    crud.update_delivery_status(db, delivery_id=delivery.id, status="completed")
                elif attempt >= MAX_ATTEMPTS:
                    crud.update_delivery_status(db, delivery_id=delivery.id, status="failed")
                else:
                    # Schedule retry if needed
                    next_attempt = attempt + 1
                    if next_attempt <= MAX_ATTEMPTS:
                        delay = RETRY_INTERVALS[attempt - 1]
                        self.schedule_task(
                            {"delivery_id": delivery_id, "attempt": next_attempt},
                            delay
                        )
                
            except requests.RequestException as e:
                # Log failed attempt
                attempt_data = schemas.DeliveryAttemptCreate(
                    delivery_id=delivery.id,
                    subscription_id=subscription.id,
                    attempt_number=attempt,
                    status_code=None,
                    success=False,
                    error=str(e)[:255]
                )
                crud.create_delivery_attempt(db, attempt_data)
                
                # Log to console/file
                log_delivery_attempt(
                    delivery_id=delivery.id,
                    subscription_id=subscription.id,
                    attempt_number=attempt,
                    status_code=None,
                    success=False,
                    error=str(e)
                )
                
                # Schedule retry if not maxed out
                if attempt < MAX_ATTEMPTS:
                    delay = RETRY_INTERVALS[attempt - 1]
                    self.schedule_task(
                        {"delivery_id": delivery_id, "attempt": attempt + 1},
                        delay
                    )
                else:
                    crud.update_delivery_status(db, delivery_id=delivery.id, status="failed")
                    
        finally:
            db.close()
    
    def schedule_task(self, task, delay_seconds):
        """Schedule a task to run after a delay"""
        task_id = str(uuid.uuid4())
        scheduled_time = time.time() + delay_seconds
        logger.info(f"Scheduling task {task_id} to run in {delay_seconds} seconds")
        self.scheduled_tasks[task_id] = (scheduled_time, task)
    
    def start(self):
        """Start the worker in a background thread"""
        if self.worker_thread and self.worker_thread.is_alive():
            logger.info("Worker is already running")
            return
            
        logger.info("Starting threaded worker...")
        self.worker_thread = threading.Thread(target=self.worker_loop)
        self.worker_thread.daemon = True  # Thread will exit when main process exits
        self.worker_thread.start()
        return {"status": "started"}
    
    def stop(self):
        """Stop the worker"""
        if self.worker_thread and self.worker_thread.is_alive():
            logger.info("Stopping worker...")
            self.running = False
            self.worker_thread.join(timeout=5)
            return {"status": "stopped"}
        return {"status": "not_running"}
    
    def status(self):
        """Check worker status"""
        is_alive = self.worker_thread and self.worker_thread.is_alive()
        queue_length = task_queue.qsize()
        scheduled = len(self.scheduled_tasks)
        
        return {
            "running": is_alive,
            "queue_length": queue_length,
            "scheduled_tasks": scheduled
        }

# Function to enqueue a delivery
def enqueue_delivery(delivery_id: str):
    """Enqueue a webhook delivery task."""
    task_queue.put({"delivery_id": delivery_id, "attempt": 1})
    logger.info(f"Enqueued delivery {delivery_id}")

# Create a singleton instance
threaded_worker = ThreadedWorker()