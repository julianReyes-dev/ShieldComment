from pydantic import BaseSettings

class Settings(BaseSettings):
    # RabbitMQ
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: str
    RABBITMQ_HOST: str
    RABBITMQ_PORT: str
    
    # Postgres
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    
    # API
    API_HOST: str
    API_PORT: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()