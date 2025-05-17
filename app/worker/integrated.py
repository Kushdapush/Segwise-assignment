import os
import threading
import logging
from redis import Redis
from rq import Queue, Worker, Connection

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("integrated-worker")

# Get Redis URL from env or use default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class IntegratedWorker:
    def __init__(self):
        self.redis_conn = Redis.from_url(REDIS_URL)
        self.queue = Queue('default', connection=self.redis_conn)
        self.worker_thread = None
        self.running = False
        
    def worker_loop(self):
        """The background worker process loop"""
        with Connection(self.redis_conn):
            worker = Worker(['default'])
            self.running = True
            logger.info(f"Starting integrated RQ worker: {worker.name}")
            worker.work(logging_level=logging.INFO)
    
    def start(self):
        """Start the worker in a background thread"""
        if self.worker_thread and self.worker_thread.is_alive():
            logger.info("Worker is already running")
            return
            
        logger.info("Starting integrated worker thread...")
        self.worker_thread = threading.Thread(target=self.worker_loop)
        self.worker_thread.daemon = True  # Thread will exit when main process exits
        self.worker_thread.start()
        return {"status": "started"}
    
    def status(self):
        """Check worker status"""
        is_alive = self.worker_thread and self.worker_thread.is_alive()
        queue_length = len(self.queue)
        
        return {
            "running": is_alive,
            "queue_length": queue_length
        }

# Create a singleton instance
integrated_worker = IntegratedWorker()