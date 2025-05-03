from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db

router = APIRouter()

@router.get("/delivery/{delivery_id}", response_model=List[schemas.DeliveryAttempt])
def get_delivery_status(delivery_id: UUID, db: Session = Depends(get_db)):
    # First check if delivery exists
    delivery = crud.get_delivery(db, delivery_id=delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
        
    attempts = crud.get_delivery_attempts(db, delivery_id=delivery_id)
    return attempts

@router.get("/subscription/{subscription_id}", response_model=List[schemas.DeliveryAttempt])
def get_subscription_attempts(subscription_id: UUID, limit: int = 20, db: Session = Depends(get_db)):
    # First check if subscription exists
    subscription = crud.get_subscription(db, subscription_id=subscription_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
        
    attempts = crud.get_subscription_attempts(db, subscription_id=subscription_id, limit=limit)
    return attempts