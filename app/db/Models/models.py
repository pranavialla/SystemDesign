from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

# For dynamic configs / maintenance mode
class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

class URLItem(Base):
    __tablename__ = "urls"

    # Numeric surrogate primary key to enable safe, collision-free short_code generation
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Short Code: unique, max 10 chars. Allow nullable during initial insert so we
    # can generate a code from the DB-assigned id.
    short_code = Column(String(10), unique=True, index=True, nullable=True)

    # Original URL: enforce uniqueness so repeated shorten requests are idempotent
    original_url = Column(String, index=True, nullable=False, unique=True)
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)
    click_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)