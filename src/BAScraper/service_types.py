from typing import Annotated, Literal, List
from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
    field_validator
)
from pydantic_extra_types.pendulum_dt import DateTime, Date
import re

EndpointTypes = Literal['submission', 'comment']

class Group:
    def __init__(self, group: List[EndpointTypes] | EndpointTypes):
        self.group: List[EndpointTypes] = group if isinstance(group, list) else [group]


class PullPushModel(BaseModel):
    """
    Docstring for PullPushModel
    """

    endpoint: EndpointTypes

    ### ⬇️ for all endpoints ⬇️ ###

    q: Annotated[  # Search term. String / Quoted String for phrases
        StrictStr | None,
        Group(['submission', 'comment']),
        Field(
            min_length=1,
            pattern=r'^(?:"[^"]*"|[^\s"]+)$'  # no spaces unless inside quoted strings
        )
    ] = None

    ids: Annotated[
        List[Annotated[
            StrictStr,
            Field(pattern=r'^[0-9a-zA-Z]+$')
        ]] | None,
        Group(['submission', 'comment']),
        Field()
    ]

    size: Annotated[
        StrictInt | None,
        Group(['submission', 'comment']),
        Field(gt=0, le=100)
    ] = None

    sort: Annotated[
        Literal['asc', 'desc'] | None,
        Group(['submission', 'comment']),
        Field()
    ] = None

    sort_type: Annotated[
        Literal['created_utc', 'score', 'num_comments'] | None,
        Group(['submission', 'comment']),
        Field()
    ] = None

    author: Annotated[
        StrictStr | None,
        Group(['submission', 'comment']),
        Field(
            min_length=3,
            max_length=20,
            pattern=r'^[A-Za-z0-9_-]$'  # Reddit username rule
        )
    ] = None

    subreddit: Annotated[
        StrictStr | None,
        Group(['submission', 'comment']),
        Field(
            min_length=1,
            max_length=20,
            pattern=r'^[A-Za-z0-9][A-Za-z0-9_]$'  # Subreddit name rule
        )
    ] = None

    after: Annotated[
        Date | DateTime | None,
        Group(['submission', 'comment']),
        Field()
    ] = None

    before: Annotated[
        Date | DateTime | None,
        Group(['submission', 'comment']),
        Field()
    ] = None

    ### ⬇️ for comment endpoint only ⬇️ ###

    link_id: Annotated[
        StrictStr | None,
        Group('comment'),
        Field(pattern=r'^[0-9a-zA-Z]+$')  # Base36 ID rule
    ] = None

    ### ⬇️ for submission endpoint only ⬇️ ###

    title: Annotated[
        StrictStr | None,
        Group('submission'),
        Field(min_length=1)
    ] = None

    selftext: Annotated[
        str | None,
        Group('submission'),
        Field(min_length=1)
    ] = None

    score: Annotated[
        StrictStr | StrictInt | None,
        Group('submission'),
        Field()
    ] = None

    num_comments: Annotated[
        StrictStr | StrictInt | None,
        Group('submission'),
        Field()
    ] = None

    over_18: Annotated[
        StrictBool | None,
        Group('submission'),
        Field()
    ] = None

    is_video: Annotated[
        StrictBool | None,
        Group('submission'),
        Field()
    ] = None

    locked: Annotated[
        StrictBool | None,
        Group('submission'),
        Field()
    ] = None

    stickied: Annotated[
        StrictBool | None,
        Group('submission'),
        Field()
    ] = None

    spoiler: Annotated[
        StrictBool | None,
        Group('submission'),
        Field()
    ] = None

    contest_mode: Annotated[
        StrictBool | None,
        Group('submission'),
        Field()
    ] = None

    @field_validator("score", "num_comments")
    def validate_operator(cls, v):
        if isinstance(v, str):
            if not re.fullmatch(r"^(?:\d+|>=\d+|<=\d+|>\d+|<\d+)$", v):
                raise ValueError("`score` field must be a valid comparison operator")
        return v

    @model_validator(mode="after")
    def check_endpoint_specific_fields(self):
        fields_set: set = self.model_fields_set
        for field_set in fields_set:
            # accessing `model_fields` via instance is depricated, only from class itself
            metadata: List[Group] = type(self).model_fields[field_set].metadata
            if len(metadata) and self.endpoint not in metadata[0].group:
                raise ValueError(
                    f"Field '{field_set}' is not valid for endpoint '{self.endpoint}'")

        return self


if __name__ == "__main__":
    test = PullPushModel(
        endpoint='submission',
        q='"test phrase"',
        ids=['abc123', 'def456'],
        size=50,
        sort='desc',
        score='>=10'
    )
