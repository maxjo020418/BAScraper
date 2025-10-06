from typing import Annotated, Literal, List
from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictInt,
    constr,
)
from pydantic_extra_types.pendulum_dt import DateTime, Date

class PullPushModel(BaseModel):
    """
    Docstring for PullPushModel
    """

    endpoint: Literal['submission', 'comment']

    q: Annotated[  # Search term. String / Quoted String for phrases
        str | None,
        Field(
            min_length=1,
            pattern=r'^(?:"[^"]*"|[^\s"]+)$'  # no spaces unless inside quoted strings
        )
    ] = None

    ids: Annotated[
        List[Annotated[
            str,
            Field(pattern=r'^[0-9a-zA-Z]+$')
        ]] | None,
        Field()
    ]

    size: Annotated[
        StrictInt | None,
        Field(gt=0, le=100)
    ] = None

    sort: Annotated[
        Literal['asc', 'desc'] | None,
        Field()
    ] = None

    sort_type: Annotated[
        Literal['created_utc', 'score', 'num_comments'] | None,
        Field()
    ] = None

    author: Annotated[
        str | None,
        Field(
            min_length=3,
            max_length=20,
            pattern=r'^[A-Za-z0-9_-]$'  # Reddit username rule
        )
    ] = None

    subreddit: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=20,
            pattern=r'^[A-Za-z0-9][A-Za-z0-9_]$'  # Subreddit name rule
        )
    ] = None

    after: Annotated[
        Date | DateTime | None,
        Field()
    ] = None

    before: Annotated[
        Date | DateTime | None,
        Field()
    ] = None

    link_id: Annotated[  # for comment endpoint only
        str | None,
        Field(pattern=r'^[0-9a-zA-Z]+$')  # Base36 ID rule
    ] = None

