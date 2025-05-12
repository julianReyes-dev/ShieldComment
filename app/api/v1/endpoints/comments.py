from app.utils.queues import COMMENT_ANALYSIS_QUEUE
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime
import json

from app.database import get_db
from app.models import Comment, CommentAnalysis, User
from app.schemas import (
    CommentCreate,
    CommentResponse,
    CommentAnalysisResponse,
    UserStatusResponse
)
from app.rabbitmq import publish_message
from app.utils.toxicity_analyzer import analyze_toxicity

router = APIRouter()

@router.post(
    "/",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new comment",
    description="Creates a new comment and queues it for toxicity analysis"
)
async def create_comment(comment: CommentCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    user = await db.get(User, comment.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is blocked
    if user.is_blocked and user.blocked_until > datetime.now():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
    try:
        await publish_message(COMMENT_ANALYSIS_QUEUE, json.dumps(message))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue comment for analysis: {str(e)}"
        )
    
    return db_comment

@router.get(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Get comment details",
    description="Retrieves details for a specific comment"
)
async def get_comment(comment_id: int, db: AsyncSession = Depends(get_db)):
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    return comment

@router.get(
    "/{comment_id}/analysis",
    response_model=CommentAnalysisResponse,
    summary="Get comment analysis",
    description="Retrieves toxicity analysis results for a comment"
)
async def get_comment_analysis(comment_id: int, db: AsyncSession = Depends(get_db)):
    analysis = await db.get(CommentAnalysis, comment_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found for this comment"
        )
    return analysis

@router.get(
    "/{comment_id}/user-status",
    response_model=UserStatusResponse,
    summary="Get user status",
    description="Retrieves moderation status for the user who made the comment"
)
async def get_user_status(comment_id: int, db: AsyncSession = Depends(get_db)):
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    
    user = await db.get(User, comment.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "user_id": user.id,
        "is_blocked": user.is_blocked,
        "blocked_until": user.blocked_until,
        "offense_count": user.offense_count
    }