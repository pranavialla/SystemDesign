from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "URL Shortener"
    
    # Infrastructure Configs (Env Vars - Required to start app)
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str
    
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    BASE_URL: str = "http://localhost:8080"

    class Config:
        env_file = ".env"

settings = Settings()
