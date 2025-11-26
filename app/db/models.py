from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class URLItem(Base):
    __tablename__ = "urls"

    short_code = Column(String(10), primary_key=True, index=True)
    original_url = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)
    click_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

# NEW: Dynamic Configuration Table
class SystemConfig(Base):
    __tablename__ = "system_configs"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
