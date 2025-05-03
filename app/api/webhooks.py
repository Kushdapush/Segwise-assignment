from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..worker.tasks import enqueue_delivery
from ..utils.security import verify_signature

router = APIRouter()

@router.post("/ingest/{subscription_id}", status_code=202)
async def ingest_webhook(
    subscription_id: UUID, 
    payload: dict = Body(...),
    signature: str = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    # Validate subscription exists
    db_subscription = crud.get_subscription(db, subscription_id=subscription_id)
    if db_subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    if not db_subscription.is_active:
        raise HTTPException(status_code=400, detail="Subscription is not active")
    
    # Verify signature if provided and secret exists
    if db_subscription.secret and signature:
        import json
        payload_str = json.dumps(payload)
        if not verify_signature(payload_str, db_subscription.secret, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Create delivery record
    delivery = schemas.DeliveryCreate(subscription_id=subscription_id, payload=payload)
    db_delivery = crud.create_delivery(db=db, delivery=delivery)
    
    # Enqueue delivery task
    background_tasks.add_task(enqueue_delivery, str(db_delivery.id))
    
    return {"message": "Webhook accepted for delivery", "delivery_id": db_delivery.id}