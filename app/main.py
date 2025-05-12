from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.api.v1.endpoints import comments, users

app = FastAPI(
    title="ShieldComment API",
    version="1.0.0",
    description="API for toxic comment detection and moderation",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with proper prefixes
app.include_router(
    comments.router,
    prefix="/api/v1/comments",
    tags=["comments"]
)
app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["users"]
)

@app.on_event("startup")
async def startup():
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created (if not exists)")

@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}