from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime

from app.database import get_db
from app.models import Comment, CommentAnalysis, User
from app.schemas import CommentCreate, CommentResponse, CommentAnalysisResponse, UserStatusResponse
from ....rabbitmq import publish_message
import json

router = APIRouter()

@router.post("/", response_model=CommentResponse)
async def create_comment(comment: CommentCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    user = await db.get(User, comment.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is blocked
    if user.is_blocked and user.blocked_until > datetime.now():
        raise HTTPException(
            status_code=403,
            detail=f"User is blocked until {user.blocked_until}"
        )
    
    # Create comment
    db_comment = Comment(text=comment.text, user_id=comment.user_id)
    db.add(db_comment)
    await db.commit()
    await db.refresh(db_comment)
    
    # Send to analysis queue
    message = {
        "comment_id": db_comment.id,
        "user_id": db_comment.user_id,
        "text": db_comment.text
    }
    await publish_message("commentAnalysisQueue", json.dumps(message))
    
    return db_comment

@router.get("/{comment_id}", response_model=CommentResponse)
async def read_comment(comment_id: int, db: AsyncSession = Depends(get_db)):
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment

@router.get("/{comment_id}/analysis", response_model=CommentAnalysisResponse)
async def read_comment_analysis(comment_id: int, db: AsyncSession = Depends(get_db)):
    analysis = await db.get(CommentAnalysis, comment_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis

@router.get("/{comment_id}/user-status", response_model=UserStatusResponse)
async def read_user_status(comment_id: int, db: AsyncSession = Depends(get_db)):
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    user = await db.get(User, comment.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,  # Usamos "id" internamente pero se expondrá como "user_id"
        "is_blocked": user.is_blocked,
        "blocked_until": user.blocked_until,
        "offense_count": user.offense_count
    }
