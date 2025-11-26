import logging
import sys

def configure_logging():
    """
    Configures application logging for production use.
    Logs to stdout with a structured, timestamped format.
    """
    # 1. Basic configuration for all loggers
    logging.basicConfig(
        level=logging.INFO,
        # Production-ready format: Timestamp | Level | Module Name | Function:Line | Message
        format='%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # 2. Configure Uvicorn/FastAPI loggers to use the same output format
    logging.getLogger("uvicorn.error").propagate = True
    # Disable default access logs; Uvicorn's default access logging can be verbose/redundant
    logging.getLogger("uvicorn.access").disabled = True 

    # 3. Suppress chattiness from libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)

    # Return the root app logger
    return logging.getLogger("app")
