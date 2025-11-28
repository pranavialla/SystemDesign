from datetime import datetime
from app.db.Connection import database
from app.db.Models import models
from app.schemas.ConfigUpdate import ConfigUpdate
from fastapi import  Depends
from sqlalchemy.orm import Session


class ConfigService:
    def save_to_db(config: ConfigUpdate, db: Session = Depends(database.get_db)):
        db_config = db.query(models.SystemConfig).filter(models.SystemConfig.key == config.key).first()
        if not db_config:
            db_config = models.SystemConfig(key=config.key, value=config.value, description=config.description)
            db.add(db_config)
        else:
            db_config.value = config.value
            db_config.description = config.description
            db_config.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(db_config)

    def save_to_redis(config: ConfigUpdate):
        database.redis_client.set(f"config:{config.key}", config.value)