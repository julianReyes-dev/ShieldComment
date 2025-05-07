import asyncio
from app.database import engine, Base, AsyncSessionLocal
from app.models import User

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create some test users
    async with AsyncSessionLocal() as db:
        users = [
            User(username="user1", email="user1@example.com"),
            User(username="user2", email="user2@example.com"),
            User(username="user3", email="user3@example.com"),
        ]
        
        for user in users:
            db.add(user)
        
        await db.commit()

if __name__ == "__main__":
    asyncio.run(init_db())
