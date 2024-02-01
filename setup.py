# run `python -m build` to build
# check https://blog.ganssle.io/articles/2021/10/setup-py-deprecated.html#summary for details

from setuptools import setup, find_packages

VERSION = '0.0.3'
DESCRIPTION = 'API wrapper for PullPush.io - the 3rd party replacement API for Reddit.'
LONG_DESCRIPTION = '''currently it can:
- get submissions/comments from a certain subreddit in supported order/sorting methods specified in the PullPush.io API docs
- get comments under the retrieved submissions
- can get all the submissions based on the number of submissions or in a certain timeframe you specify
- can recover(if possible) deleted/removed submission/comments from the returned result
check the [documentation on the github](https://github.com/maxjo020418/BAScraper) for detailed info
'''

# Setting up
setup(
    name="BAScraper",
    version=VERSION,
    author="maxjo",
    author_email="jo@yeongmin.net",
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    long_description=LONG_DESCRIPTION,
    packages=find_packages(),
    install_requires=['requests'],

    keywords=['reddit scraper', 'reddit', 'scraper', 'pullpush', 'wrapper'],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
    ],
    python_requires=">=3.8",
    project_urls={
      'Github': 'https://github.com/maxjo020418/BAScraper'
    }
)