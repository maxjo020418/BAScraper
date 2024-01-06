# BAScraper
A little (multithreaded) API wrapper for [PullPush.io](https://www.pullpush.io/) - the 3rd party replacement API for Reddit. After the [2023 Reddit API controversy](https://en.wikipedia.org/wiki/2023_Reddit_API_controversy), 
PushShift.io(and also wrappers such as PSAW and PMAW) is now only availale to reddit admins and Reddit PRAW is honestly useless when trying to get a lots of data and data from a specific timeframe.
PullPush.io thankfully solves this issue and this is the wrapper for that said API. For more info on the API(TOS, Forum, Docs, etc.) go to [PullPush.io](https://www.pullpush.io/).

BAScraper(Blue Archive Scraper) was initially made and used for the 2023 recap/wrap up of r/BlueArchive hence the name.
It's pretty basic but planning to add some more features as it goes. I'm also planning to release this as a python package. (this is my first time making an actual py package so bear with me)
It uses multithreading to make requests to the PullPush.io endpoint and returns the result as a JSON(dict) object.

currently it can:
- get submissions from a certain subreddit in supported order/sorting methods specified in the PullPush.io API docs
- get comments under the retrieved submissions
- can get all the submissions based on the number of submissions or in a certain timeframe you specify

I also have a tool that can organize, clean, and analyze reddit submission and comment data, which I am planning to release it with this or seperately after some polishing.

Also please ask the PullPush.io owner before making large amounts or request and also respect cooldown times. It stresses the server and can cause inconvenience for everyone.

## basic usage & requirements
this is not yet a python package so this is the rundown on how to use it and set up.

put the BAscraper.py in your working directory and import it with the following dependancies:
```
requests
time
logging
json
dataclasses -> dataclass
typing -> List
datetime -> datetime, timedelta
concurrent.futures -> ThreadPoolExecutor, as_completed
queue -> Queue
```
The only non-default package is `requests`, any version should be fine. also python 3.7+ is recommended due to the use of `dataclasses` (which is not used yet but is planned to).

**Example usage**
```python
from BAscraper import Pushpull

import requests
import time
import logging
import json
from dataclasses import dataclass
from typing import List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

pp = Pushpull(sleepsec=2, threads=2)
result = pp.get_submissions(after=datetime(2023, 12, 1), before=datetime(2024, 1, 1),
                               subreddit='bluearchive', sort='desc')

# save result as JSON
with open("example.json", "w", encoding='utf-8') as outfile:
    json.dump(result, outfile, indent=4)
```

# parameters
-
