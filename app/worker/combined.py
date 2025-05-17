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
        if self.worker:
            self.worker.request_stop()
        
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
            if self.worker:
                worker_state = self.worker.get_state()
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

# Create a global worker instance
combined_worker = CombinedWorker()