from BAScraper.service_types import ArcticShiftModel
from BAScraper.service_types import PullPushModel

from BAScraper import BAScraper
from BAScraper.utils import BAConfig

import datetime
import pendulum

import asyncio
import json

def main():
    # !! config(validation run) needs to be run before model validation if you want logs
    # !! because logging config is done within BAConfig model validation (init.)
    conf = BAConfig(
            # log_level=logging.DEBUG,
            log_file_path="bascraper.log",
            log_file_mode="w",
        )

    example1 = ArcticShiftModel(
        no_workers=3,
        no_sub_comment_workers=10,
        interval_sleep_ms=250,
        endpoint="posts",
        lookup="search",
        # ids=["123123","23we"],
        subreddit="r/umamusume",
        after="2025-10-25",
        before="2025-10-25T12:00:00Z",
        # sort="asc",
        # limit=50,
        # title="release",
        fields=["title", "link_flair_text"],
        fetch_post_comments=True
    )
    print(example1.model_dump_json(indent=4, exclude_none=True))

    print(f"\n{30*"="}\n")

    example2 = PullPushModel(
        endpoint="comment",
        q='"test phrase"',
        ids=['abc123', 'def456'],
        size=50,
        sort='desc',
        # score='>=10',
        # title="eee",
        # over_18=True,
        after=datetime.datetime(2025, 1, 1), # "2023-01-01",
        before=pendulum.datetime(2026, 10, 2), #"2026-10-26T15:30:00Z",
    )
    print(example2.model_dump_json(indent=4, exclude_none=True))

    bas = BAScraper(conf)
    res = asyncio.run(bas.get(example1))

    with open("test.json", "w+") as f:
        json.dump(res, f, indent=4)


if __name__ == "__main__":
    main()
