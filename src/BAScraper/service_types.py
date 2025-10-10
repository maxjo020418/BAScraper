from typing import Annotated, Literal, List, Self, Union
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


ArcticShiftEndpointTypes = Literal[
    'posts', 'comments', 'subreddits', 'users',
    'short_links', 'time_series'
]
ArcticShiftLookupTypes = Literal[
    'ids', 'search', # all (4 main stuffs)
    'aggregate',  # posts, comments
    'tree',  # comments
    'rules', 'wikis', 'wikis/list'  # subreddits
    'interactions/users', 'interactions/users/list', 'interactions/subreddits',  # users
    'flairs',  # users (aggregated flairs)
]

class ArcticShiftGroup:
    def __init__(self,
                 group: Union[
                     List[ArcticShiftEndpointTypes],
                     ArcticShiftEndpointTypes,
                    ],
                 lookup_type: Union[
                     List[ArcticShiftLookupTypes],
                     ArcticShiftLookupTypes,
                 ]
    ) -> None:
        self.group: List[ArcticShiftEndpointTypes] = \
            group if isinstance(group, list) else [group]
        self.lookup_type: List[ArcticShiftLookupTypes] = \
            lookup_type if isinstance(lookup_type, list) else [lookup_type]

###############################################################

class PullPushModel(BaseModel):
    """
    Docstring for PullPushModel
    """
    _BASE_URL: StrictStr = "https://api.pullpush.io/reddit/search"
    endpoint: PullPushEndpointTypes

    no_coro: Annotated[
        StrictInt,
        Field(gt=0)
    ] = 3  # number of coroutines

    interval_sleep_ms: Annotated[
        StrictInt,
        Field(ge=0)
    ] = 500

    # TODO: check if there are duplicate results and add duplicate handling if needed.

    ### ⬇️ for all endpoints ⬇️ ###

    q: Annotated[  # Search term. String / Quoted String for phrases
        StrictStr | None,
        PullPushGroup(['submission', 'comment']),
        Field(
            min_length=1,
            pattern=r'^(?:"[^"]*"|[^\s"]+)$'  # no spaces unless inside quoted strings
        )
    ] = None

    ids: Annotated[
        List[Annotated[
            StrictStr,
            Field(pattern=r'^[0-9a-zA-Z]+$')
        ]] | str | None,
        PullPushGroup(['submission', 'comment']),
        Field()
    ] = None

    size: Annotated[
        StrictInt | None,
        PullPushGroup(['submission', 'comment']),
        Field(gt=0, le=100)
    ] = None

    sort: Annotated[
        Literal['asc', 'desc'] | None,
        PullPushGroup(['submission', 'comment']),
        Field()
    ] = None

    sort_type: Annotated[
        Literal['created_utc', 'score', 'num_comments'] | None,
        PullPushGroup(['submission', 'comment']),
        Field()
    ] = None

    author: Annotated[
        StrictStr | None,
        PullPushGroup(['submission', 'comment']),
        Field(
            min_length=3,
            max_length=20,
            pattern=r'^[A-Za-z0-9_-]$'  # Reddit username rule
        )
    ] = None

    subreddit: Annotated[
        StrictStr | None,
        PullPushGroup(['submission', 'comment']),
        Field(
            min_length=1,
            max_length=20,
            pattern=r'^[A-Za-z0-9][A-Za-z0-9_]$'  # Subreddit name rule
        )
    ] = None

    after: Annotated[
        DateTime | int | None,
        PullPushGroup(['submission', 'comment']),
        Field()
    ] = None

    before: Annotated[
        DateTime | int | None,
        PullPushGroup(['submission', 'comment']),
        Field()
    ] = None

    ### ⬇️ for comment endpoint only ⬇️ ###

    link_id: Annotated[
        StrictStr | None,
        PullPushGroup('comment'),
        Field(pattern=r'^[0-9a-zA-Z]+$')  # Base36 ID rule
    ] = None

    ### ⬇️ for submission endpoint only ⬇️ ###

    title: Annotated[
        StrictStr | None,
        PullPushGroup('submission'),
        Field(min_length=1)
    ] = None

    selftext: Annotated[
        StrictStr | None,
        PullPushGroup('submission'),
        Field(min_length=1)
    ] = None

    score: Annotated[
        StrictStr | StrictInt | None,
        PullPushGroup('submission'),
        Field()
    ] = None

    num_comments: Annotated[
        StrictStr | StrictInt | None,
        PullPushGroup('submission'),
        Field()
    ] = None

    over_18: Annotated[
        StrictBool | None,
        PullPushGroup('submission'),
        Field(deprecated="This field is not supported as of now by PullPush")
    ] = None

    is_video: Annotated[
        StrictBool | None,
        PullPushGroup('submission'),
        Field(deprecated="This field is not supported as of now by PullPush")
    ] = None

    locked: Annotated[
        StrictBool | None,
        PullPushGroup('submission'),
        Field(deprecated="This field is not supported as of now by PullPush")
    ] = None

    stickied: Annotated[
        StrictBool | None,
        PullPushGroup('submission'),
        Field(deprecated="This field is not supported as of now by PullPush")
    ] = None

    spoiler: Annotated[
        StrictBool | None,
        PullPushGroup('submission'),
        Field(deprecated="This field is not supported as of now by PullPush")
    ] = None

    contest_mode: Annotated[
        StrictBool | None,
        PullPushGroup('submission'),
        Field(deprecated="This field is not supported as of now by PullPush")
    ] = None

    @field_validator("score", "num_comments")
    @classmethod
    def validate_operator(cls, v) -> str:
        if isinstance(v, str):
            if not re.fullmatch(r"^(?:\d+|>=\d+|<=\d+|>\d+|<\d+)$", v):
                raise ValueError("`score` field must be a valid comparison operator")
        return v

    @model_validator(mode="after")
    def check_endpoint_specific_fields(self) -> Self:
        fields_set: set = self.model_fields_set
        for field_set in fields_set:
            # accessing `model_fields` via instance is deprecated,
            # should be accessed only from class itself
            metadata: List[PullPushGroup] = type(self).model_fields[field_set].metadata
            if len(metadata) and self.endpoint not in metadata[0].group:
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


class ArcticShiftModel(BaseModel):
    """
    Docstring for ArcticShiftModel
    """
    _BASE_URL: StrictStr = "arctic-shift.photon-reddit.com/api"
    endpoint: ArcticShiftEndpointTypes

    no_coro: Annotated[
        StrictInt,
        Field(gt=0)
    ] = 3  # number of coroutines

    interval_sleep_ms: Annotated[
        StrictInt,
        Field(ge=0)
    ] = 500


if __name__ == "__main__":
    test = PullPushModel(
        endpoint='submission',
        q='"test phrase"',
        ids=['abc123', 'def456'],
        size=50,
        sort='desc',
        score='>=10',
        over_18=True
    )
    print(test.over_18)
    print(test.model_dump())
