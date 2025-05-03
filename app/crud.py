from sqlalchemy.orm import Session
from sqlalchemy.sql import desc
from uuid import UUID
import json
from . import models, schemas

# Subscription CRUD
def create_subscription(db: Session, subscription: schemas.SubscriptionCreate):
    db_subscription = models.Subscription(
        target_url=str(subscription.target_url),
        secret=subscription.secret,
        event_types=subscription.event_types
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def get_subscription(db: Session, subscription_id: UUID):
    return db.query(models.Subscription).filter(models.Subscription.id == subscription_id).first()

def get_subscriptions(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Subscription).offset(skip).limit(limit).all()

def update_subscription(db: Session, subscription_id: UUID, subscription: schemas.SubscriptionUpdate):
    db_subscription = db.query(models.Subscription).filter(models.Subscription.id == subscription_id).first()
    
    if db_subscription is None:
        return None
        
    update_data = subscription.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key == "target_url" and value:
            setattr(db_subscription, key, str(value))
        else:
            setattr(db_subscription, key, value)
            
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

def delete_subscription(db: Session, subscription_id: UUID):
    db_subscription = db.query(models.Subscription).filter(models.Subscription.id == subscription_id).first()
    if db_subscription:
        db.delete(db_subscription)
        db.commit()
    return db_subscription

# Delivery CRUD
def create_delivery(db: Session, delivery: schemas.DeliveryCreate):
    db_delivery = models.Delivery(
        subscription_id=delivery.subscription_id,
        payload=delivery.payload
    )
    db.add(db_delivery)
    db.commit()
    db.refresh(db_delivery)
    return db_delivery

def get_delivery(db: Session, delivery_id: UUID):
    return db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()

def update_delivery_status(db: Session, delivery_id: UUID, status: str):
    db_delivery = db.query(models.Delivery).filter(models.Delivery.id == delivery_id).first()
    if db_delivery:
        db_delivery.status = status
        db.commit()
        db.refresh(db_delivery)
    return db_delivery

# DeliveryAttempt CRUD
def create_delivery_attempt(db: Session, attempt: schemas.DeliveryAttemptCreate):
    db_attempt = models.DeliveryAttempt(
        delivery_id=attempt.delivery_id,
        subscription_id=attempt.subscription_id,
        attempt_number=attempt.attempt_number,
        status_code=attempt.status_code,
        success=attempt.success,
        error=attempt.error
    )
    db.add(db_attempt)
    db.commit()
    db.refresh(db_attempt)
    return db_attempt

def get_delivery_attempts(db: Session, delivery_id: UUID):
    return db.query(models.DeliveryAttempt).filter(
        models.DeliveryAttempt.delivery_id == delivery_id
    ).order_by(desc(models.DeliveryAttempt.timestamp)).all()

def get_subscription_attempts(db: Session, subscription_id: UUID, limit: int = 20):
    return db.query(models.DeliveryAttempt).filter(
        models.DeliveryAttempt.subscription_id == subscription_id
    ).order_by(desc(models.DeliveryAttempt.timestamp)).limit(limit).all()

def delete_old_attempts(db: Session, hours: int = 72):
    """Delete attempts older than specified hours"""
    from datetime import datetime, timedelta
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    db.query(models.DeliveryAttempt).filter(
        models.DeliveryAttempt.timestamp < cutoff_time
    ).delete()
    
    db.commit()