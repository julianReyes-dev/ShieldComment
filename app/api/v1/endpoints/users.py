from sqlalchemy import select, and_
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User
from app.schemas import UserCreate, UserResponse
from app.database import get_db

router = APIRouter()

@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Verifica si el usuario ya existe
    existing_user = await db.execute(
        select(User).where(User.username == user.username)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    existing_email = await db.execute(
        select(User).where(User.email == user.email)
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Crea el nuevo usuario
    db_user = User(
        username=user.username,
        email=user.email,
        offense_count=0,
        is_blocked=False,
        blocked_until=None
    )
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/blocked", summary="Get currently blocked users")
async def get_blocked_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .where(and_(
            User.is_blocked == True,
            User.blocked_until > datetime.utcnow()
        ))
        .order_by(User.blocked_until.desc())
    )
    
    users = result.scalars().all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "offense_count": user.offense_count,
            "blocked_until": user.blocked_until
        }
        for user in users
    ]

@router.get("/blocked", summary="Get currently blocked users")
async def get_blocked_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .where(User.is_blocked == True)
        .where(User.blocked_until > datetime.utcnow())
        .order_by(User.blocked_until.desc())
    )
    
    users = result.scalars().all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "offense_count": user.offense_count,
            "blocked_until": user.blocked_until
        }
        for user in users
    ]