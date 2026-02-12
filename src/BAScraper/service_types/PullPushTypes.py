from typing import (
    Annotated,
    Any,
    Literal,
    List,
    Self,
    Union,
    ClassVar,
    Tuple,
)

from datetime import datetime
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from tzlocal import get_localzone
from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
    field_validator,
)

from pydantic_extra_types.pendulum_dt import DateTime
import re

from BAScraper.utils import (
    reddit_username_rule,
    reddit_id_rule,
    subreddit_name_rule,
    localize_temporal_fields,
    normalize_datetime_fields,
    validate_temporal_order,
    validate_temporal_value,
)

ServiceType = Literal["PullPush"]

PullPushEndpointTypes = Literal['submission', 'comment']

class PullPushGroup:
    def __init__(self,
                 group: Union[
                     List[PullPushEndpointTypes],
                     PullPushEndpointTypes,
                    ]
    ) -> None:
        self.group: List[PullPushEndpointTypes] = \
            group if isinstance(group, list) else [group]

###############################################################

class PullPushModel(BaseModel):
    """
    Pydantic model describing all supported Arctic Shift API parameters.
    """
    _BASE_URL: StrictStr = "https://api.pullpush.io/reddit/search"
    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

    service_type: ServiceType | None = None  # only used when passed in as dict (for identification)
    timezone: StrictStr = Field(default=get_localzone().key,
                                validate_default=True)

    endpoint: PullPushEndpointTypes

    no_workers: StrictInt = Field(default=3, gt=0)  # number of coroutines
    interval_sleep_ms: StrictInt = Field(default=500, ge=0)
    cooldown_sleep_ms: StrictInt = Field(default=5000, ge=0)
    max_retries: int = Field(default=10, ge=0)
    backoff_factor: int | float = Field(default=1, ge=0)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
            cls.logger.info(f"Timezone set as: {v}")
        except ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {v}")
        return v

    @model_validator(mode="before")
    @classmethod
    def localize_temporal_fields(cls, data: Any) -> Any:
        return localize_temporal_fields(
            data,
            cls._TEMPORAL_FIELDS,
            cls.logger,
        )

    ### for all endpoints ###

    q: Annotated[  # Search term. String / Quoted String for phrases
        StrictStr | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(
        default=None,
        min_length=1,
        pattern=r'^(?:"[^"]*"|[^\s"]+)$'  # no spaces unless inside quoted strings
    )

    ids: Annotated[
        List[Annotated[
            StrictStr,
            Field(pattern=reddit_id_rule)
        ]] | str | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(default=None)

    size: Annotated[
        StrictInt | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(default=None, gt=0, le=100)

    sort: Annotated[
        Literal['asc', 'desc'] | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(default=None)

    sort_type: Annotated[
        Literal['created_utc', 'score', 'num_comments'] | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(default=None)

    author: Annotated[
        StrictStr | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(default=None, pattern=reddit_username_rule)

    subreddit: Annotated[
        StrictStr | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(default=None, pattern=subreddit_name_rule)

    after: Annotated[
        DateTime | datetime | StrictInt | StrictStr | None,
        PullPushGroup(['submission', 'comment'])
        # StrictStr type is ONLY FOR IDE LINTERS
        # Strings not matching DateTime format would be caught later
    ] = Field(default=None, union_mode="left_to_right")

    before: Annotated[
        DateTime | datetime | StrictInt | StrictStr | None,
        PullPushGroup(['submission', 'comment'])
        # StrictStr type is ONLY FOR IDE LINTERS
        # Strings not matching DateTime format would be caught later
    ] = Field(default=None, union_mode="left_to_right")

    ### for comment endpoint only ###

    link_id: Annotated[
        StrictStr | None,
        PullPushGroup('comment')
    ] = Field(default=None, pattern=reddit_id_rule)  # Base36 ID rule

    ### for submission endpoint only ###

    title: Annotated[
        StrictStr | None,
        PullPushGroup('submission')
    ] = Field(default=None, min_length=1)

    selftext: Annotated[
        StrictStr | None,
        PullPushGroup('submission')
    ] = Field(default=None, min_length=1)

    score: Annotated[
        StrictStr | StrictInt | None,
        PullPushGroup('submission')
    ] = Field(default=None)

    num_comments: Annotated[
        StrictStr | StrictInt | None,
        PullPushGroup('submission')
    ] = Field(default=None)

    over_18: Annotated[
        StrictBool | None,
        PullPushGroup('submission')
    ] = Field(default=None, deprecated="This field is not supported as of now by PullPush")

    is_video: Annotated[
        StrictBool | None,
        PullPushGroup('submission')
    ] = Field(default=None, deprecated="This field is not supported as of now by PullPush")

    locked: Annotated[
        StrictBool | None,
        PullPushGroup('submission')
    ] = Field(default=None, deprecated="This field is not supported as of now by PullPush")

    stickied: Annotated[
        StrictBool | None,
        PullPushGroup('submission')
    ] = Field(default=None, deprecated="This field is not supported as of now by PullPush")

    spoiler: Annotated[
        StrictBool | None,
        PullPushGroup('submission')
    ] = Field(default=None, deprecated="This field is not supported as of now by PullPush")

    contest_mode: Annotated[
        StrictBool | None,
        PullPushGroup('submission')
    ] = Field(default=None, deprecated="This field is not supported as of now by PullPush")

    @field_validator("score", "num_comments")
    @classmethod
    def validate_operator(cls, v: str | int | None) -> str | int | None:
        if isinstance(v, str):
            if not re.fullmatch(r"^(?:\d+|>=\d+|<=\d+|>\d+|<\d+)$", v):
                raise ValueError("`score` field must be a valid comparison operator")
        return v

    _TEMPORAL_FIELDS: ClassVar[Tuple[str, ...]] = ("after", "before")

    @field_validator(*_TEMPORAL_FIELDS, mode="after")
    @classmethod
    def validate_temporal_value(cls, value: DateTime | datetime | int | str | None):
        return validate_temporal_value(value)

    @field_validator("ids")
    @classmethod
    def check_id_list(cls, v: str | List[StrictStr]) -> StrictStr:
        if isinstance(v, list):
            return ','.join(v)
        else:
            return v
            # TODO:
            #   if string(else), validate if it's in `<id>,<id>,<id>,...` form

    @model_validator(mode="after")
    def check_endpoint_specific_fields(self) -> Self:
        for field_set in self.model_fields_set:  # per field that is set
            # accessing `model_fields` via instance is deprecated,
            # should be accessed only from class itself
            metadata = type(self).model_fields[field_set].metadata
            for meta in metadata:  # metadata(s) per field
                if isinstance(meta, PullPushGroup):
                    if self.endpoint not in meta.group:
                        raise ValueError(
                            f"Field '{field_set}' is not supported for endpoint '{self.endpoint}'")
        return self

    @model_validator(mode="after")
    def check_date_order(self) -> Self:  # also convert datetime to epoch
        normalize_datetime_fields(self, self._TEMPORAL_FIELDS, self.timezone, self.logger)
        validate_temporal_order(self.after, self.before)

        return self
