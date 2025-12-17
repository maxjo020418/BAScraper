from typing import Any, Dict, Literal
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime
from pprint import pformat
from pydantic import BaseModel, Field, field_validator
from tzlocal import get_localzone
import pathlib

from .extra_validators import *

class BAConfig(BaseModel):
    timezone: str = Field(default=get_localzone().key, validate_default=True)
    logging_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            "handlers": [logging.StreamHandler()],
        }
    )
    log_level: LOG_LEVELS = Field(default=logging.INFO)
    log_file_path: str = Field(
        default=f"BAScraper-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log",
        validate_default=True
    )
    log_file_mode: VALID_MODES = Field(default="a")
    log_stream: bool = Field(default=True)

    """
    logging.FileHandler(
                    filename=f"BAScraper-{datetime.now().strftime("%Y-%m-%d_%H:%M:%S")}.log", 
                    mode='a'
                    )
    """

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {v}")
        return v
    
    @field_validator("log_file_path")
    def validate_file_path(cls, path: str) -> str:
        p = validate_output_path(pathlib.Path(path))
        return str(p)
    
    def model_post_init(self, context: Any) -> None:
        # just in case
        self.logging_config.setdefault('handlers', [])

        if 'logging_config' not in self.model_fields_set:
            self.logging_config['handlers'].append(
                logging.FileHandler(
                    filename=self.log_file_path, 
                    mode=self.log_file_mode,
                )
            )
            self.logging_config['level'] = self.log_level

        logger = logging.getLogger(__name__)
        logging.basicConfig(**self.logging_config)

        logger.info(f"TZ set as: {self.timezone}\n" \
                    f"Logging settings:\n{pformat(self.logging_config, indent=4)}")

