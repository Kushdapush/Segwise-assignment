import os
import threading
import logging
from redis import Redis
from rq import Queue, Worker

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("combined-worker")

# Get Redis URL from env or use default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class CombinedWorker:
    def __init__(self):
        self.redis_conn = Redis.from_url(REDIS_URL)
        self.queue = Queue(connection=self.redis_conn)
        self.worker = Worker([self.queue], connection=self.redis_conn)
        self.thread = None

    def run_worker(self):
        """Run the worker loop."""
        logger.info("Worker loop starting...")
        try:
            # `burst=False` means it will keep running
            self.worker.work(burst=False, logging_level="INFO")
        except Exception as e:
            logger.exception("Worker crashed with error")

    def start(self):
        """Start the worker in a background thread."""
        if self.thread and self.thread.is_alive():
            logger.info("Worker is already running")
            return

        logger.info("Starting worker thread...")
        self.thread = threading.Thread(target=self.run_worker, daemon=True)
        self.thread.start()

    def enqueue_job(self, func, *args, **kwargs):
        """Add a job to the queue."""
        try:
            job = self.queue.enqueue(func, *args, **kwargs)
            logger.info(f"Job {job.id} enqueued successfully")
            return job.id
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            return None

    def status(self):
        """Return simple status info."""
        return {
            "thread_alive": self.thread.is_alive() if self.thread else False,
            "queue_length": len(self.queue),
            "worker_name": self.worker.name
        }

# Global instance
combined_worker = CombinedWorker()
