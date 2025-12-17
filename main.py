from BAScraper.service_types import ArcticShiftModel
from BAScraper.service_types import PullPushModel

from BAScraper import BAScraper
from BAScraper.utils import BAConfig

import logging

def main():
    try:
        example = ArcticShiftModel(
            endpoint="comments",
            lookup="ids",
            ids=["123123","23we"],
            # subreddit="r/python",
            # after="2023-01-01",
            # # before="2023-10-26T15:30:00Z",
            # sort="asc",
            # limit=50,
            # title="release",
            fields=["id", "title", "created_utc"],
        )
        print(example.model_dump_json(indent=4, exclude_none=True))

        print(f"\n{30*"="}\n")

        example = PullPushModel(
            endpoint="comment",
            q='"test phrase"',
            ids=['abc123', 'def456'],
            size=50,
            sort='desc',
            # score='>=10',
            # title="eee",
            # over_18=True,
        )
        print(example.model_dump_json(indent=4, exclude_none=True))

    except Exception as e:
        raise(e)

    bas = BAScraper(
        BAConfig(
            log_level=logging.DEBUG,
            log_file_path="bascraper.log",
            log_file_mode="w",
        )
    )


if __name__ == "__main__":
    main()
