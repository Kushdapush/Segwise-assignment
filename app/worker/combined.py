import os
import time
import threading
import logging
from redis import Redis
from rq import Queue, Worker
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("combined-worker")

# Environment variables
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

class CombinedWorker:
    """A worker thread that runs inside the web service."""
    
    def __init__(self):
        self.redis_conn = None
        self.queue = None
        self.worker = None
        self.stop_event = threading.Event()
        self.retry_interval = 5  # seconds
        self.thread = None
        self.worker_id = f"worker-{os.getpid()}"
    
    def initialize(self):
        """Initialize Redis connection."""
        try:
            logger.info("Initializing combined worker...")
            self.redis_conn = Redis.from_url(REDIS_URL)
            # Test connection but handle potential errors gracefully
            try:
                self.redis_conn.ping()
                logger.info("Redis ping successful")
            except Exception as e:
                logger.error(f"Redis ping failed: {str(e)}")
                # Continue anyway as some Redis errors are non-fatal
            
            self.queue = Queue(connection=self.redis_conn)
            queue_length = 0
            try:
                queue_length = len(self.queue)
            except:
                logger.warning("Could not get queue length")
            
            logger.info(f"Combined worker initialized. Queue length: {queue_length}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {str(e)}")
            return False
    
    def run_worker(self):
        """Run the worker process inside a thread."""
        logger.info("Starting worker thread...")
        
        while not self.stop_event.is_set():
            try:
                # Create a new worker - we need to recreate on each loop
                # since we're using a custom checking mechanism
                logger.info("Creating new RQ worker...")
                worker = Worker([self.queue], connection=self.redis_conn, name=self.worker_id)
                self.worker = worker
                
                logger.info("Worker polling for jobs...")
                
                # Custom job processing loop instead of worker.work()
                # This avoids the signal handler issue
                while not self.stop_event.is_set():
                    try:
                        # Check for jobs and process one if available
                        job = worker.reserve(timeout=1)
                        if job:
                            logger.info(f"Processing job {job.id}")
                            worker.perform_job(job)
                        else:
                            # Sleep briefly to avoid CPU spinning
                            time.sleep(0.1)
                    except Exception as e:
                        logger.error(f"Error processing job: {str(e)}")
                        time.sleep(1)  # Avoid tight loop on errors
                
            except Exception as e:
                logger.error(f"Worker error: {str(e)}")
                
                # Attempt to reconnect
                logger.info("Attempting to reconnect in 5 seconds...")
                time.sleep(5)
                try:
                    # Test connection
                    self.redis_conn.ping()
                except:
                    # Re-initialize if ping fails
                    logger.info("Reinitializing Redis connection...")
                    self.initialize()
    
    def start(self):
        """Start the worker thread."""
        if self.thread and self.thread.is_alive():
            logger.info("Worker thread is already running")
            return
        
        if not self.initialize():
            logger.error("Failed to initialize worker. Will retry in background.")
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run_worker, daemon=True)
        self.thread.start()
        logger.info(f"Worker thread started with ID {self.worker_id}")
    
    def stop(self):
        """Stop the worker thread."""
        logger.info("Stopping worker thread...")
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=5.0)
            logger.info("Worker thread stopped")
    
    def status(self):
        """Get worker status."""
        if not self.thread or not self.thread.is_alive():
            return {"status": "stopped"}
            
        queue_length = 0
        worker_state = "unknown"
        current_job = None
        
        try:
            queue_length = len(self.queue) if self.queue else 0
            worker_state = "running" if self.worker else "not initialized"
            
            # Use a safer approach to get current job
            if hasattr(self.worker, 'get_current_job'):
                job = self.worker.get_current_job()
                if job:
                    current_job = {
                        "id": job.id,
                        "description": job.description
                    }
        except Exception as e:
            logger.error(f"Error getting status: {str(e)}")
            
        return {
            "status": "running" if self.thread and self.thread.is_alive() else "stopped",
            "queue_length": queue_length,
            "worker_state": worker_state,
            "current_job": current_job,
            "thread_alive": self.thread.is_alive() if self.thread else False
        }
    
    def enqueue_job(self, function, *args, **kwargs):
        """Helper to enqueue jobs directly through this worker."""
        if not self.queue:
            if not self.initialize():
                logger.error("Failed to initialize queue for job")
                return None
        
        try:
            job = self.queue.enqueue(function, *args, **kwargs)
            logger.info(f"Successfully enqueued job {job.id}")
            return job.id
        except Exception as e:
            logger.error(f"Failed to enqueue job: {str(e)}")
            return None

# Create a global worker instance
combined_worker = CombinedWorker()