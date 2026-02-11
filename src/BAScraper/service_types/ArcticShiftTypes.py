from __future__ import annotations

from typing import (
    Annotated,
    ClassVar,
    Dict,
    List,
    Literal,
    Optional,
    Self,
    Tuple,
    Union,
    Callable
)

from datetime import datetime
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from tzlocal import get_localzone

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from BAScraper.utils import (
    reddit_username_rule,
    reddit_id_rule,
    subreddit_name_rule,
    localize_temporal_fields,
    normalize_datetime_fields,
    validate_temporal_order,
    validate_temporal_value,
)
from BAScraper.service_types.PullPushTypes import PullPushModel

from pydantic_extra_types.pendulum_dt import DateTime
import re

ArcticShiftEndpointTypes = Literal[
    "posts",
    "comments",
    "subreddits",
    "users",
    "short_links",
    "time_series",
]

ArcticShiftLookupTypes = Literal[
    "ids",
    "search",
    "search/aggregate",
    "tree",
    "rules",
    "wikis",
    "wikis/list",
    "interactions/users",
    "interactions/users/list",
    "interactions/subreddits",
    "aggregate_flairs",
    None,  # for time_series and short_links
]

_CommonField = Literal[
    "author",
    "author_fullname",
    "author_flair_text",
    "created_utc",
    "distinguished",
    "id",
    "retrieved_on",
    "subreddit",
    "subreddit_id",
    "score",
]

_PostOnlyField = Literal[
    "crosspost_parent",
    "link_flair_text",
    "num_comments",
    "over_18",
    "post_hint",
    "selftext",
    "spoiler",
    "title",
    "url",
]

_CommentOnlyField = Literal[
    "body",
    "link_id",
    "parent_id",
]

SubredditField = Literal[
    "created_utc",
    "description",
    "public_description",
    "display_name",
    "id",
    "over18",
    "retrieved_on",
    "subscribers",
    "title",
    # add "_meta*" names here if they are concrete strings
]

PostField = Union[_CommonField, _PostOnlyField]
CommentField = Union[_CommonField, _CommentOnlyField]
AllFields = Union[PostField, CommentField, SubredditField]

TimeSeriesPrecision = Literal["year", "quarter", "month", "week",
                              "day", "hour", "minute"]

REDDIT_ID_RE = re.compile(reddit_id_rule)
SUBREDDIT_RE = re.compile(subreddit_name_rule)
MAX_IDS = 500
MAX_SUBREDDITS = 1000
MAX_WIKI_PATHS = 100
MAX_SHORT_LINK_PATHS = 1000


class ArcticShiftGroup:
    """
    Associates fields with `endpoint/lookup` combinations so they can be validated later on.

    Note:
    ArcticShiftGroup metadata structure is
    ```python
        List[
            Tuple[
                List[endpoints: ArcticShiftEndpointTypes],
                List[lookups: ArcticShiftLookupTypes]
            ]
        ]
    ```
    each tuple in the list is the possible combinations of endpoints and lookups that the field is valid for.
    (is used for URI endpoint construction)

    example use in `ArcticShiftModel`:
    ```python
        md2html: Annotated[
            StrictBool | None,
            ArcticShiftGroup(
                [
                    (["posts", "comments", "subreddits", "users"], ["ids"]),
                    (["posts", "comments"], ["search"]),
                    (["comments"], ["tree"]),
                ]
            ),
        ] = Field(default=None)
    ```
    can be interpreted as:

    parameter `md2html` is type `StrictBool | None` with default val of `None`,
    and is used/valid on the following endpoints:
    ```
        /api/posts/ids
        /api/comments/ids
        /api/subreddits/ids
        /api/users/ids

        /api/posts/search
        /api/comments/search

        /api/comments/tree
    ```
    so a possible `4*1 + 2*1 + 1*1 = 7` endpoints
    """

    def __init__(
        self,
        group: List[
            Tuple[
                List[ArcticShiftEndpointTypes],
                List[Optional[ArcticShiftLookupTypes]],
            ]
        ],
    ) -> None:
        self.group = group


class ArcticShiftModel(BaseModel):
    """
    Pydantic model describing all supported Arctic Shift API parameters.
    """

    _BASE_URL: StrictStr = "https://arctic-shift.photon-reddit.com/api/"
    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

    service_type: StrictStr | None = None  # only used when passed in as dict (for identification)
    timezone: StrictStr = Field(default=get_localzone().key,
                                validate_default=True)

    endpoint: ArcticShiftEndpointTypes
    lookup: ArcticShiftLookupTypes

    no_coro: StrictInt = Field(default=3, gt=0)
    interval_sleep_ms: StrictInt = Field(default=500, ge=0)
    cooldown_sleep_ms: StrictInt = Field(default=5000, ge=0)
    max_retries: int = Field(default=10, ge=0)
    backoff_factor: int | float = Field(default=1, ge=0)

    # default val None won't fetch comments under post
    # if a service Model is set, it'll use that setting/model to fetch comments
    fetch_post_comments: ArcticShiftModel | PullPushModel | None = Field(default=None)

    @field_validator("fetch_post_comments")
    @classmethod
    def validate_fetch_post_comments_model(
        cls, v: ArcticShiftModel | PullPushModel | None):
        if v is None:
            return v
        assert v.endpoint == "comment" or v.endpoint == "comments", \
            "`fetch_post_comments` field is used for fetching comments, " \
            f"set the `endpoint` field to fetch comments, not as `{v.endpoint}`"
        return v

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
    def localize_temporal_fields(cls, data):
        return localize_temporal_fields(
            data,
            cls._TEMPORAL_FIELDS,
            cls.logger,
        )

    ## OPTIONAL API FIELDS ##

    ids: Annotated[
        List[Annotated[StrictStr, Field(pattern=reddit_id_rule)]] | StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments", "subreddits", "users"], ["ids"]),
            ]
        ),
    ] = Field(default=None, max_length=MAX_IDS)

    md2html: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["posts", "comments", "subreddits", "users"], ["ids"]),
                (["posts", "comments"], ["search"]),
                (["comments"], ["tree"]),
            ]
        ),
    ] = Field(default=None)

    fields: Annotated[
        List[PostField | CommentField | SubredditField] | StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments", "subreddits", "users"], ["ids"]),
                (["posts", "comments", "subreddits"], ["search"]),
            ]
        ),
    ] = Field(default=None)

    author: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search", "search/aggregate"]),
                (
                    ["users"],
                    [
                        "search",
                        "interactions/users",
                        "interactions/users/list",
                        "interactions/subreddits",
                        "aggregate_flairs",
                    ],
                ),
            ]
        ),
    ] = Field(default=None, pattern=reddit_username_rule)

    subreddit: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search", "search/aggregate"]),
                (["subreddits"], ["search", "wikis", "wikis/list"]),
                (
                    ["users"],
                    ["interactions/users", "interactions/users/list", "interactions/subreddits"],
                ),
            ]
        ),
    ] = Field(default=None, pattern=subreddit_name_rule)

    author_flair_text: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search", "search/aggregate"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    after: Annotated[
        DateTime | datetime | StrictInt | StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search", "search/aggregate"]),
                (["subreddits"], ["search"]),
                (
                    ["users"],
                    ["interactions/users", "interactions/users/list", "interactions/subreddits"],
                ),
                (["time_series"], [None]),
            ]
        ),
        # StrictStr type is ONLY FOR IDE LINTERS
        # Strings not matching DateTime format would be caught later
    ] = Field(default=None, union_mode="left_to_right")

    before: Annotated[
        DateTime | datetime | StrictInt | StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search", "search/aggregate"]),
                (["subreddits"], ["search"]),
                (
                    ["users"],
                    ["interactions/users", "interactions/users/list", "interactions/subreddits"],
                ),
                (["time_series"], [None]),
            ]
        ),
        # StrictStr type is ONLY FOR IDE LINTERS
        # Strings not matching DateTime format would be caught later
    ] = Field(default=None, union_mode="left_to_right")

    limit: Annotated[
        StrictInt | Literal["auto"] | Literal[""] | None,
        ArcticShiftGroup(
            [
                (["posts", "comments", "subreddits", "users"], ["search"]),
                (["comments"], ["tree"]),
                (["subreddits"], ["wikis"]),
                (["posts", "comments"], ["search/aggregate"]),
                (
                    ["users"],
                    ["interactions/users", "interactions/users/list", "interactions/subreddits"],
                ),
            ]
        ),
    ] = Field(default=100)

    sort: Annotated[
        Literal["asc", "desc"] | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search", "search/aggregate"]),
                (["subreddits"], ["search"]),
                (["users"], ["search"]),
            ]
        )
    ] = Field(default=None)

    crosspost_parent_id: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None)

    over_18: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None)

    spoiler: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None)

    title: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    selftext: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    link_flair_text: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    query: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    url: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    url_exact: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
    ] = Field(default=None)

    body: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["comments"], ["search"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    link_id: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["comments"], ["search", "tree"]),
            ]
        ),
    ] = Field(default=None)

    parent_id: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["comments"], ["search", "tree"]),
            ]
        ),
    ] = Field(default=None)

    start_breadth: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["comments"], ["tree"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    start_depth: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["comments"], ["tree"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    aggregate: Annotated[
        Literal["created_utc", "author", "subreddit"] | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search/aggregate"]),
            ]
        ),
    ] = Field(default=None)

    frequency: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search/aggregate"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    min_count: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search/aggregate"]),
                (
                    ["users"],
                    ["interactions/users", "interactions/users/list", "interactions/subreddits"],
                ),
            ]
        ),
    ] = Field(default=None, ge=0)

    subreddit_prefix: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
            ]
        ),
    ] = Field(default=None, pattern=subreddit_name_rule)

    min_subscribers: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    max_subscribers: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    over18: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
            ]
        ),
    ] = Field(default=None)

    sort_type: Annotated[
        Literal["created_utc", "subscribers", "subreddit", "author", "total_karma"] | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
                (["users"], ["search"]),
            ]
        ),
    ] = Field(default=None)

    subreddits: Annotated[
        List[Annotated[StrictStr, Field(pattern=subreddit_name_rule)]] | StrictStr | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["rules"]),
            ]
        ),
    ] = Field(default=None, max_length=MAX_SUBREDDITS)

    paths: Annotated[
        List[StrictStr] | StrictStr | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["wikis"]),
                (["short_links"], [None]),
            ]
        ),
    ] = Field(default=None)

    author_prefix: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    min_num_posts: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    min_num_comments: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    active_since: Annotated[
        DateTime | datetime | StrictInt | StrictStr | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
        # StrictStr type is ONLY FOR IDE LINTERS
        # Strings not matching DateTime format would be caught later
    ] = Field(default=None, union_mode="left_to_right")

    min_karma: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    weight_posts: Annotated[
        StrictFloat | None,
        ArcticShiftGroup(
            [
                (["users"], ["interactions/subreddits"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    weight_comments: Annotated[
        StrictFloat | None,
        ArcticShiftGroup(
            [
                (["users"], ["interactions/subreddits"]),
            ]
        ),
    ] = Field(default=None, ge=0)

    key: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["time_series"], [None]),
            ]
        ),
    ] = Field(default=None, min_length=1)

    precision: Annotated[
        TimeSeriesPrecision | None,
        ArcticShiftGroup(
            [
                (["time_series"], [None]),
            ]
        ),
    ] = Field(default=None)

    _ALLOWED_LOOKUPS: ClassVar[
        Dict[ArcticShiftEndpointTypes, set[Optional[ArcticShiftLookupTypes]]]
    ] = {
        "posts": {"ids", "search", "search/aggregate"},
        "comments": {"ids", "search", "tree", "search/aggregate"},
        "subreddits": {"ids", "search", "rules", "wikis", "wikis/list"},
        "users": {
            "ids",
            "search",
            "interactions/users",
            "interactions/users/list",
            "interactions/subreddits",
            "aggregate_flairs",
        },
        "short_links": {None},
        "time_series": {None},
    }

    _TEMPORAL_FIELDS: ClassVar[Tuple[str, ...]] = ("after", "before", "active_since")

    @staticmethod
    def _strip_user_prefix(value: str) -> str:
        if value[:2].lower() == "u/":
            return value[2:]
        return value

    @staticmethod
    def _strip_subreddit_prefix(value: str) -> str:
        if value[:2].lower() == "r/":
            return value[2:]
        return value

    @field_validator("author", "author_prefix", mode="before")
    @classmethod
    def normalize_author(cls, value: str | None):
        if isinstance(value, str):
            return cls._strip_user_prefix(value)
        return value

    @field_validator("subreddit", "subreddit_prefix", mode="before")
    @classmethod
    def normalize_subreddit(cls, value: str | None):
        if isinstance(value, str):
            return cls._strip_subreddit_prefix(value)
        return value

    @field_validator("parent_id", "link_id", "crosspost_parent_id", mode="before")
    @classmethod
    def validate_single_id(cls, value: str | None):
        if isinstance(value, str):
            if not len(value):  # empty str
                return value
            assert REDDIT_ID_RE.fullmatch(value)
        else:  # when None
            return value

    @field_validator(*_TEMPORAL_FIELDS, mode="after")
    @classmethod
    def validate_temporal_value(cls, value: DateTime | datetime | int | str | None):
        return validate_temporal_value(value)

    @field_validator("fields", mode="after")
    @classmethod
    def validate_fields(cls, value: List[AllFields] | StrictStr):
        # `id` and `created_utc` must be included to index/paginate
        if isinstance(value, str):
            value_temp: List[str] = [value]
        elif isinstance(value, list):
            value_temp = value.copy() # type: ignore

        if 'created_utc' not in value:
            value_temp.append('created_utc')
        if 'id' not in value:
            value_temp.append('id')

        return value_temp

    @model_validator(mode="after")
    def validate_lookup(self) -> Self:
        allowed = self._ALLOWED_LOOKUPS[self.endpoint]
        if self.lookup not in allowed:
            allowed_values = \
                f"\"lookup field not needed for `{self.endpoint}`\"" \
                if None in allowed else ", ".join(sorted(str(item) for item in allowed if item))
            raise ValueError(
                f"Lookup '{self.lookup}' is not supported for endpoint '{self.endpoint}'. "
                f"Allowed values: {allowed_values}"
            )

        for field_name in self.model_fields_set:
            # accessing `model_fields` via instance is deprecated,
            # should be accessed only from class itself
            metadata = type(self).model_fields[field_name].metadata

            # metadatas is a list of metadata(Attributes) within the set fields (model_fields_set)
            # below checks/finds `ArcticShiftGroup` exists within the metadata(s)
            group_meta = next(
                    (meta for meta in metadata if isinstance(meta, ArcticShiftGroup)), 
                    None
                )
            if not group_meta:  # skip if no `ArcticShiftGroup` is found
                continue

            valid_combination = False
            for endpoints, lookups in group_meta.group:
                if self.endpoint not in endpoints:
                    continue
                if (
                    (self.lookup is None and None in lookups)
                    or (self.lookup is not None and self.lookup in lookups)
                ):
                    valid_combination = True
                    break
            if not valid_combination:
                raise ValueError(
                    f"Field '{field_name}' is not supported for endpoint '{self.endpoint}' "
                    f"with lookup '{self.lookup}'"
                )

        return self

    @model_validator(mode="after")
    def normalize_and_validate(self) -> Self:
        self._validate_required_fields()
        self._normalise_lists()
        self._normalize_datetime_fields()
        self._validate_temporal_order()
        self._validate_limit()
        self._validate_frequency_requirement()
        return self

    def _validate_required_fields(self) -> None:
        if self.lookup == "ids" and not self.ids:
            raise ValueError("The 'ids' parameter is required when using the ids lookup.")

        if self.endpoint == "comments" and self.lookup == "tree" and not self.link_id:
            raise ValueError("'link_id' is required for the comments/tree endpoint.")

        if self.endpoint == "subreddits" and self.lookup == "rules" and not self.subreddits:
            raise ValueError("'subreddits' is required for the subreddits/rules endpoint.")

        if self.endpoint == "subreddits" and self.lookup == "wikis/list" and not self.subreddit:
            raise ValueError("'subreddit' is required for the subreddits/wikis/list endpoint.")

        if self.endpoint == "subreddits" and self.lookup == "wikis":
            if not self.paths and not self.subreddit:
                raise ValueError(
                    "Either 'paths' or 'subreddit' must be supplied for the subreddits/wikis endpoint."
                )

        if self.endpoint == "users" and self.lookup in {
            "interactions/users",
            "interactions/users/list",
            "interactions/subreddits",
            "aggregate_flairs",
        }:
            if not self.author:
                raise ValueError("'author' is required for the selected users endpoint.")

        if self.endpoint == "short_links" and not self.paths:
            raise ValueError("'paths' is required for the short_links endpoint.")

        if self.endpoint == "time_series":
            if not self.key:
                raise ValueError("'key' is required for the time_series endpoint.")
            if not self.precision:
                raise ValueError("'precision' is required for the time_series endpoint.")

        if self.lookup == "search/aggregate" and not self.aggregate:
            raise ValueError("'aggregate' is required when using the search/aggregate lookup.")

    def _normalise_lists(self) -> None:
        if self.ids is not None:
            self.ids = self._convert_to_csv(self.ids, MAX_IDS, REDDIT_ID_RE, "ids")

        if self.fields is not None:
            self.fields = self._convert_to_csv(self.fields, None, None, "fields")

        if self.subreddits is not None:
            self.subreddits = self._convert_to_csv(
                self.subreddits,
                MAX_SUBREDDITS,
                SUBREDDIT_RE,
                "subreddits",
                transform=self._strip_subreddit_prefix,
            )

        if self.paths is not None:
            max_paths = MAX_SHORT_LINK_PATHS if self.endpoint == "short_links" else MAX_WIKI_PATHS
            self.paths = self._convert_to_csv(self.paths, max_paths, None, "paths")

    @staticmethod
    def _convert_to_csv(
        value: Union[List[str], List[AllFields], StrictStr],
        max_items: Optional[int],
        pattern: Optional[re.Pattern[str]],
        field_name: str,
        transform: Callable[[str], str] | None = None,
    ) -> str:
        if isinstance(value, list):
            items = value
        else:
            items = [item.strip() for item in value.split(",") if item.strip()]

        if transform:
            items = [transform(item) for item in items]

        if max_items is not None and len(items) > max_items:
            raise ValueError(f"'{field_name}' accepts at most {max_items} entries.")

        if pattern:
            for item in items:
                if not pattern.fullmatch(item):
                    raise ValueError(f"'{field_name}' entry '{item}' does not match the required format.")

        return ",".join(items)

    def _normalize_datetime_fields(self) -> None:
        normalize_datetime_fields(self, self._TEMPORAL_FIELDS, self.timezone, self.logger)

    def _validate_temporal_order(self) -> None:
        validate_temporal_order(self.after, self.before)

    def _validate_limit(self) -> None:
        if self.limit is None:
            return

        limit_value = self.limit

        if self.lookup == "search":
            if self.endpoint in {"posts", "comments"}:
                if limit_value == "auto":
                    return
                if isinstance(limit_value, int) and 1 <= limit_value <= 100:
                    return
                raise ValueError("For posts/comments search, 'limit' must be between 1 and 100 or 'auto'.")
            if self.endpoint == "subreddits":
                if isinstance(limit_value, int) and 1 <= limit_value <= 1000:
                    return
                raise ValueError("For subreddit search, 'limit' must be between 1 and 1000.")
            if self.endpoint == "users":
                if isinstance(limit_value, int) and 1 <= limit_value <= 1000:
                    return
                raise ValueError("For users search, 'limit' must be between 1 and 1000.")

            raise ValueError(f"'limit' is not supported for {self.endpoint}/{self.lookup}.")

        if self.endpoint == "comments" and self.lookup == "tree":
            if isinstance(limit_value, int) and 1 <= limit_value <= 25_000:
                return
            raise ValueError("For comments/tree, 'limit' must be between 1 and 25000.")

        if self.endpoint == "subreddits" and self.lookup == "wikis":
            if isinstance(limit_value, int) and 1 <= limit_value <= 100:
                return
            raise ValueError("For subreddits/wikis, 'limit' must be between 1 and 100.")

        if self.lookup == "search/aggregate":
            if limit_value == "" or (isinstance(limit_value, int) and limit_value >= 1):
                return
            raise ValueError(
                "For search/aggregate, 'limit' must be >= 1 or an empty string to remove the limit."
            )

        if self.lookup in {"interactions/users", "interactions/users/list", "interactions/subreddits"}:
            if limit_value == "" or (isinstance(limit_value, int) and limit_value >= 1):
                return
            raise ValueError(
                "For user interaction endpoints, 'limit' must be >= 1 or empty to remove the limit."
            )

        raise ValueError(f"'limit' is not supported for {self.endpoint}/{self.lookup}.")

    def _validate_frequency_requirement(self) -> None:
        if self.lookup == "search/aggregate" and self.aggregate == "created_utc":
            if not self.frequency:
                raise ValueError(
                    "'frequency' is required when aggregate=created_utc for the search/aggregate lookup."
                )
