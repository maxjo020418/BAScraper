from typing import Any, Dict, Literal
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from tzlocal import get_localzone

log_levels = Literal[
    10, # logging.DEBUG
    20, # logging.INFO
    30, # logging.WARNING
    40, # logging.ERROR
    50, # logging.CRITICAL
]

class BAConfig(BaseModel):
    timezone: str = Field(default=get_localzone().key, validate_default=True)
    logging_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "level": logging.INFO,
            "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            "filename": f"BAScraper-{datetime.now().strftime("%Y-%m-%d_%H:%M:%S")}.log",
            "filemode": "a",
            "handlers": [
                logging.StreamHandler()
            ],
        }
    )
    log_level: log_levels = Field(default=logging.INFO)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {v}")
        return v
    
    def model_post_init(self, context: Any) -> None:
        logger = logging.getLogger(__name__)
        logging.basicConfig(*self.logging_config)

        logger.info(f"TZ set as: {self.timezone}\n" \
                    f"Log level set as: {self.log_level} @ {self.logging_config['filename']}")

