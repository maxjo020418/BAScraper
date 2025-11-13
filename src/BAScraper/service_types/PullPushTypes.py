from typing import (
    Annotated, 
    Literal, 
    List, 
    Self, 
    Union
)
from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
    field_validator
)
from pydantic_extra_types.pendulum_dt import DateTime
import re

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

reddit_id_rule = r'^[0-9a-zA-Z]+$'  # Base36 ID rule
reddit_username_rule = r'^[A-Za-z0-9_-]{3,20}$'  # Reddit username rule
subreddit_name_rule = r'^[A-Za-z0-9][A-Za-z0-9_]{1,20}$'  # Subreddit name rule

###############################################################

class PullPushModel(BaseModel):
    """
    Docstring for PullPushModel
    """
    _BASE_URL: StrictStr = "https://api.pullpush.io/reddit/search"
    endpoint: PullPushEndpointTypes

    no_coro: StrictInt = Field(default=3, gt=0)  # number of coroutines

    interval_sleep_ms: StrictInt = Field(default=500, ge=0)

    # TODO: check if there are duplicate results and add duplicate handling if needed.

    ### ⬇️ for all endpoints ⬇️ ###

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
        DateTime | int | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(default=None)

    before: Annotated[
        DateTime | int | None,
        PullPushGroup(['submission', 'comment'])
    ] = Field(default=None)

    ### ⬇️ for comment endpoint only ⬇️ ###

    link_id: Annotated[
        StrictStr | None,
        PullPushGroup('comment')
    ] = Field(default=None, pattern=reddit_id_rule)  # Base36 ID rule

    ### ⬇️ for submission endpoint only ⬇️ ###

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
        if isinstance(self.after, DateTime):
            self.after = self.after.int_timestamp
        if isinstance(self.before, DateTime):
            self.before = self.before.int_timestamp

        if self.after and self.before and self.after >= self.before:
            raise ValueError("'after' must be less than 'before'")

        if self.after and not self.before:
            pass

        return self

    @model_validator(mode='after')
    def check_id_list(self) -> Self:
        if isinstance(self.ids, list):
            self.ids = ','.join(self.ids)

        # TODO:
        #   if string(else), validate if it's in `<id>,<id>,<id>,...` form

        return self
