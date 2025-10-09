from typing import Union
import httpx

from BAScraper.service_types import PullPushModel

def get(settings: Union[PullPushModel, dict]):
    if not isinstance(settings, PullPushModel):
        settings = PullPushModel.model_validate(settings)

    pass
