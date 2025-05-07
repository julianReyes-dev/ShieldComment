from fastapi import FastAPI
from app.database import engine, Base
from app.api.v1.endpoints import comments, users

# Crea la instancia de FastAPI
app = FastAPI(title="ShieldComment API", version="1.0.0")

# Configuración de CORS (si es necesaria)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluye los routers
app.include_router(comments.router, prefix="/api/v1/comments", tags=["comments"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])

# Crea tablas de la base de datos al iniciar
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
