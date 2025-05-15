from app.utils.queues import COMMENT_ANALYSIS_QUEUE
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from datetime import datetime
import json
import os

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

# Configurar templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../../templates"))

@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def get_dashboard():
    return templates.TemplateResponse("index.html", {"request": {}})

@router.get("/recent", summary="Get recent analyzed comments")
async def get_recent_comments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment, CommentAnalysis, User)
        .join(CommentAnalysis, Comment.id == CommentAnalysis.comment_id)
        .join(User, Comment.user_id == User.id)
        .order_by(CommentAnalysis.analyzed_at.desc())
        .limit(20)
    )
    
    comments = []
    for comment, analysis, user in result:
        comments.append({
            "id": comment.id,
            "text": comment.text,
            "created_at": comment.created_at,
            "user": {
                "id": user.id,
                "username": user.username
            },
            "analysis": {
                "toxicity_score": analysis.toxicity_score,
                "classification": analysis.classification,
                "analyzed_at": analysis.analyzed_at
            }
        })
    
    return comments

@router.get("/stats", summary="Get toxicity statistics")
async def get_toxicity_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            func.sum(func.case((CommentAnalysis.classification == "non-toxic", 1), else_=0)).label("non_toxic"),
            func.sum(func.case((CommentAnalysis.classification == "potentially-toxic", 1), else_=0)).label("potentially_toxic"),
            func.sum(func.case((CommentAnalysis.classification == "toxic", 1), else_=0)).label("toxic")
        )
    )
    
    stats = result.first()
    return {
        "non_toxic": stats.non_toxic or 0,
        "potentially_toxic": stats.potentially_toxic or 0,
        "toxic": stats.toxic or 0
    }

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