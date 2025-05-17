import os
import time
import threading
import logging
from redis import Redis
from rq import Queue, Worker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("combined-worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class CombinedWorker:
    def __init__(self):
        self.redis_conn = Redis.from_url(REDIS_URL)
        self.queue = Queue(connection=self.redis_conn)
        self.worker = Worker([self.queue], connection=self.redis_conn)
        self.thread = None
        self.stop_event = threading.Event()

    def run_worker(self):
        logger.info("Worker thread started")
        try:
            self.worker.work(burst=False, with_scheduler=False, logging_level="INFO", stop_when_empty=False)
        except Exception as e:
            logger.exception("Worker thread crashed")

    def start(self):
        if self.thread and self.thread.is_alive():
            logger.info("Worker already running")
            return

        self.thread = threading.Thread(target=self.run_worker, daemon=True)
        self.thread.start()

    def stop(self):
        logger.info("Stopping worker (manual shutdown not supported directly by RQ)")
        self.stop_event.set()

    def enqueue_job(self, func, *args, **kwargs):
        job = self.queue.enqueue(func, *args, **kwargs)
        logger.info(f"Enqueued job {job.id}")
        return job.id
