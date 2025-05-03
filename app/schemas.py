from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
from pydantic import BaseModel, HttpUrl

class SubscriptionBase(BaseModel):
    target_url: HttpUrl
    secret: Optional[str] = None
    event_types: Optional[List[str]] = None

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(BaseModel):
    target_url: Optional[HttpUrl] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None
    event_types: Optional[List[str]] = None

class Subscription(SubscriptionBase):
    id: UUID
    created_at: datetime
    is_active: bool

    class Config:
        orm_mode = True
        from_attributes = True

class WebhookPayload(BaseModel):
    data: Dict[str, Any]

class DeliveryBase(BaseModel):
    subscription_id: UUID
    payload: Dict[str, Any]

class DeliveryCreate(DeliveryBase):
    pass

class Delivery(DeliveryBase):
    id: UUID
    created_at: datetime
    status: str

    class Config:
        orm_mode = True
        from_attributes = True

class DeliveryAttemptBase(BaseModel):
    delivery_id: UUID
    subscription_id: UUID
    attempt_number: int
    status_code: Optional[int] = None
    success: bool
    error: Optional[str] = None

class DeliveryAttemptCreate(DeliveryAttemptBase):
    pass

class DeliveryAttempt(DeliveryAttemptBase):
    id: UUID
    timestamp: datetime

    class Config:
        orm_mode = True
        from_attributes = True