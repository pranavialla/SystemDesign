from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Build the SQLAlchemy DB URL from settings
DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:"
    f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:"
    f"{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI dependency: yield a SQLAlchemy session and ensure it's closed.
    Usage: db: Session = Depends(database.get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
