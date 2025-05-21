from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from app.database import engine, Base
from app.api.v1.endpoints import comments, users

# Crea la instancia de FastAPI
app = FastAPI(
    title="ShieldComment API",
    version="1.0.0",
    description="API for toxic comment detection and moderation",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configuración de archivos estáticos y templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluye los routers
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

# Crea tablas de la base de datos al iniciar
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created (if not exists)")

@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}