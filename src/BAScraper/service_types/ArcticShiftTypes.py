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
)

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

from pydantic_extra_types.pendulum_dt import DateTime
import re
import warnings

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

TimeSeriesPrecision = Literal["year", "quarter", "month", "week", "day", "hour", "minute"]

reddit_id_rule = r"^(?:t[1-6]_[0-9A-Za-z]{2,}|[0-9A-Za-z]+)$"
reddit_username_rule = r"^(?:u/)?[A-Za-z0-9_-]{3,20}$"
subreddit_name_rule = r"^(?:r/)?[A-Za-z0-9][A-Za-z0-9_]{1,20}$"

REDDIT_ID_RE = re.compile(reddit_id_rule)
SUBREDDIT_RE = re.compile(subreddit_name_rule)
MAX_IDS = 500
MAX_SUBREDDITS = 1000
MAX_WIKI_PATHS = 100
MAX_SHORT_LINK_PATHS = 1000


class ArcticShiftGroup:
    """
    Associates fields with endpoint/lookup combinations so they can be validated later on.

    Note:
    ArcticShiftGroup metadata structure is
    List[
        Tuple[
            List[endpoints: ArcticShiftEndpointTypes],
            List[lookups: ArcticShiftLookupTypes]
        ]
    ]
    each tuple in the list is the possible combinations of endpoints and lookups that the field is valid for.
    (+ is used for URI endpoint construction)
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

    _BASE_URL: StrictStr = "https://arctic-shift.photon-reddit.com/api"
    endpoint: ArcticShiftEndpointTypes
    lookup: Optional[ArcticShiftLookupTypes] = "search"

    no_coro: Annotated[StrictInt, Field(gt=0)] = 3
    interval_sleep_ms: Annotated[StrictInt, Field(ge=0)] = 500

    ids: Annotated[
        List[Annotated[StrictStr, Field(pattern=reddit_id_rule)]] | StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments", "subreddits", "users"], ["ids"]),
            ]
        ),
        Field(max_length=MAX_IDS),
    ] = None

    md2html: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["posts", "comments", "subreddits", "users"], ["ids"]),
                (["posts", "comments"], ["search"]),
                (["comments"], ["tree"]),
            ]
        ),
        Field(),
    ] = None

    fields: Annotated[
        List[PostField | CommentField | SubredditField] | StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments", "subreddits", "users"], ["ids"]),
                (["posts", "comments", "subreddits"], ["search"]),
            ]
        ),
        Field(),
    ] = None

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
        Field(pattern=reddit_username_rule),
    ] = None

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
        Field(pattern=subreddit_name_rule),
    ] = None

    author_flair_text: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search", "search/aggregate"]),
            ]
        ),
        Field(min_length=1),
    ] = None

    after: Annotated[
        DateTime | StrictInt | StrictStr | None,
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
        Field(union_mode="left_to_right"),
    ] = None

    before: Annotated[
        DateTime | StrictInt | StrictStr | None,
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
        Field(union_mode="left_to_right"),
    ] = None

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
        Field(),
    ] = None

    sort: Annotated[
        Literal["asc", "desc"] | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search", "search/aggregate"]),
                (["subreddits"], ["search"]),
                (["users"], ["search"]),
            ]
        ),
        Field(),
    ] = None

    crosspost_parent_id: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(pattern=reddit_id_rule),
    ] = None

    over_18: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(),
    ] = None

    spoiler: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(),
    ] = None

    title: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(min_length=1),
    ] = None

    selftext: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(min_length=1),
    ] = None

    link_flair_text: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(min_length=1),
    ] = None

    query: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(min_length=1),
    ] = None

    url: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(min_length=1),
    ] = None

    url_exact: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["posts"], ["search"]),
            ]
        ),
        Field(),
    ] = None

    body: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["comments"], ["search"]),
            ]
        ),
        Field(min_length=1),
    ] = None

    link_id: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["comments"], ["search", "tree"]),
            ]
        ),
        Field(pattern=reddit_id_rule),
    ] = None

    parent_id: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["comments"], ["search", "tree"]),
            ]
        ),
        Field(),
    ] = None

    start_breadth: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["comments"], ["tree"]),
            ]
        ),
        Field(ge=0),
    ] = None

    start_depth: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["comments"], ["tree"]),
            ]
        ),
        Field(ge=0),
    ] = None

    aggregate: Annotated[
        Literal["created_utc", "author", "subreddit"] | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search/aggregate"]),
            ]
        ),
        Field(),
    ] = None

    frequency: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["posts", "comments"], ["search/aggregate"]),
            ]
        ),
        Field(min_length=1),
    ] = None

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
        Field(ge=0),
    ] = None

    subreddit_prefix: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
            ]
        ),
        Field(pattern=subreddit_name_rule),
    ] = None

    min_subscribers: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
            ]
        ),
        Field(ge=0),
    ] = None

    max_subscribers: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
            ]
        ),
        Field(ge=0),
    ] = None

    over18: Annotated[
        StrictBool | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
            ]
        ),
        Field(),
    ] = None

    sort_type: Annotated[
        Literal["created_utc", "subscribers", "subreddit", "author", "total_karma"] | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["search"]),
                (["users"], ["search"]),
            ]
        ),
        Field(),
    ] = None

    subreddits: Annotated[
        List[Annotated[StrictStr, Field(pattern=subreddit_name_rule)]] | StrictStr | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["rules"]),
            ]
        ),
        Field(max_length=MAX_SUBREDDITS),
    ] = None

    paths: Annotated[
        List[StrictStr] | StrictStr | None,
        ArcticShiftGroup(
            [
                (["subreddits"], ["wikis"]),
                (["short_links"], [None]),
            ]
        ),
        Field(),
    ] = None

    author_prefix: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
        Field(min_length=1),
    ] = None

    min_num_posts: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
        Field(ge=0),
    ] = None

    min_num_comments: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
        Field(ge=0),
    ] = None

    active_since: Annotated[
        DateTime | StrictInt | StrictStr | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
        # StrictStr type is ONLY FOR IDE LINTERS
        # Strings not matching DateTime format would be caught later
        Field(union_mode="left_to_right"),
    ] = None

    min_karma: Annotated[
        StrictInt | None,
        ArcticShiftGroup(
            [
                (["users"], ["search"]),
            ]
        ),
        Field(ge=0),
    ] = None

    weight_posts: Annotated[
        StrictFloat | None,
        ArcticShiftGroup(
            [
                (["users"], ["interactions/subreddits"]),
            ]
        ),
        Field(ge=0),
    ] = None

    weight_comments: Annotated[
        StrictFloat | None,
        ArcticShiftGroup(
            [
                (["users"], ["interactions/subreddits"]),
            ]
        ),
        Field(ge=0),
    ] = None

    key: Annotated[
        StrictStr | None,
        ArcticShiftGroup(
            [
                (["time_series"], [None]),
            ]
        ),
        Field(min_length=1),
    ] = None

    precision: Annotated[
        TimeSeriesPrecision | None,
        ArcticShiftGroup(
            [
                (["time_series"], [None]),
            ]
        ),
        Field(),
    ] = None

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
    def normalize_author(cls, value):
        if isinstance(value, str):
            return cls._strip_user_prefix(value)
        return value

    @field_validator("subreddit", "subreddit_prefix", mode="before")
    @classmethod
    def normalize_subreddit(cls, value):
        if isinstance(value, str):
            return cls._strip_subreddit_prefix(value)
        return value

    @field_validator("parent_id", "link_id", "crosspost_parent_id", mode="before")
    @classmethod
    def validate_single_id(cls, value):
        if value in (None, ""):
            return value
        if isinstance(value, str) and REDDIT_ID_RE.fullmatch(value):
            return value
        raise ValueError("Value must be a valid reddit base36 id")

    @field_validator(*_TEMPORAL_FIELDS, mode="after")
    @classmethod
    def validate_temporal_value(cls, value):
        if isinstance(value, str):
            raise ValueError("Value must be a valid datetime (ISO 8601) or integer timestamp (epoch)")
        return value

    @model_validator(mode="after")
    def validate_lookup(self) -> Self:
        allowed = self._ALLOWED_LOOKUPS[self.endpoint]
        if self.lookup not in allowed:
            allowed_values = ", ".join(sorted(str(item) for item in allowed if item))
            suffix = " or no lookup" if None in allowed else ""
            raise ValueError(
                f"Lookup '{self.lookup}' is not supported for endpoint '{self.endpoint}'. "
                f"Allowed values: {allowed_values}{suffix}"
            )

        for field_name in self.model_fields_set:
            metadata = type(self).model_fields[field_name].metadata
            group_meta = next((meta for meta in metadata if isinstance(meta, ArcticShiftGroup)), None)
            if not group_meta:
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
        transform=None,
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
        for attr in self._TEMPORAL_FIELDS:
            value = getattr(self, attr)
            if isinstance(value, DateTime):  # pass for int and None
                setattr(self, attr, value.int_timestamp)

    def _validate_temporal_order(self) -> None:
        # after and before should be either None or int now
        if isinstance(self.after, int) and isinstance(self.before, int):
            if self.after >= self.before:
                raise ValueError("'after' must be less than 'before'.")
        elif self.after is not None and self.before is None:
            warnings.warn("'after' is set but 'before' is not, " \
            "BAScraper will not attempt to iterate and will only fetch a single page of results.", UserWarning)
        elif self.after is None and isinstance(self.before, int):
            warnings.warn("'before' is set but 'after' is not, " \
            "BAScraper will not attempt to iterate and will only fetch a single page of results.", UserWarning)
        else:  # both None
            warnings.warn("'after' and 'before' are both None, " \
            "BAScraper will not attempt to iterate and will only fetch a single page of results.", UserWarning)

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


if __name__ == "__main__":
    # Example usage and validation
    try:
        example = ArcticShiftModel(
            endpoint="posts",
            lookup="search",
            subreddit="r/python",
            # after="2023-01-01",
            # before="2023-10-26T15:30:00Z",
            limit=50,
            sort="desc",
            title="release",
            fields=["id", "title", "created_utc"],
        )
        print(example.model_dump_json(indent=4, exclude_none=True))
    except Exception as e:
        print(f"Error:\n{e}")

