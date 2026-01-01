from __future__ import annotations

from typing import Any, Dict
import logging
from datetime import datetime
from pprint import pformat
from pydantic import BaseModel, Field, field_validator
import pathlib

from .extra_validators import LOG_LEVELS, VALID_MODES, validate_output_path

class BAConfig(BaseModel):
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

    @field_validator("log_file_path")
    @classmethod
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

        logger.debug(f"Logging settings:\n{pformat(
                self.logging_config |
                {
                    "log_file_path": self.log_file_path,
                    "log_file_mode": self.log_file_mode,
                    "log_stream": self.log_stream
                },
                indent=4)}")
