import logging
import json
from datetime import datetime
from uuid import UUID

# Configure logger
logger = logging.getLogger("webhook_service")
logger.setLevel(logging.INFO)

# Handler
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def log_delivery_attempt(delivery_id, subscription_id, attempt_number, status_code, success, error=None):
    """Log a webhook delivery attempt."""
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "delivery_id": str(delivery_id),
        "subscription_id": str(subscription_id),
        "attempt": attempt_number,
        "status_code": status_code,
        "success": success
    }
    
    if error:
        log_data["error"] = str(error)
    
    if success:
        logger.info(f"Webhook delivery succeeded: {json.dumps(log_data)}")
    else:
        logger.warning(f"Webhook delivery failed: {json.dumps(log_data)}")

class WebhookLogger:
    """Helper class for webhook logging"""
    
    @staticmethod
    def subscription_created(subscription_id: UUID, target_url: str):
        logger.info(f"Subscription created: id={subscription_id}, url={target_url}")
    
    @staticmethod
    def subscription_updated(subscription_id: UUID):
        logger.info(f"Subscription updated: id={subscription_id}")
    
    @staticmethod
    def subscription_deleted(subscription_id: UUID):
        logger.info(f"Subscription deleted: id={subscription_id}")
    
    @staticmethod
    def webhook_received(subscription_id: UUID, delivery_id: UUID):
        logger.info(f"Webhook received: subscription={subscription_id}, delivery={delivery_id}")