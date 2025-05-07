from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Optional

class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    user_id: int
    
class CommentResponse(BaseModel):
    id: int
    text: str
    user_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class CommentAnalysisResponse(BaseModel):
    id: int
    comment_id: int
    toxicity_score: int
    classification: str
    analyzed_at: datetime
    
    class Config:
        orm_mode = True

class UserStatusResponse(BaseModel):
    id: int = Field(..., alias="user_id")
    is_blocked: bool
    blocked_until: Optional[datetime]
    offense_count: int
    
    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    offense_count: int = 0
    is_blocked: bool = False
    blocked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
