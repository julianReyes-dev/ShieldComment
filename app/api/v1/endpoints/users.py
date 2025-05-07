from sqlalchemy import select
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
