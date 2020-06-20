Ycrawler
========
a training project for training asynchronous programming skills. The program downloads the news from news.ycombinator.com, 30 topics and links in comments.

Params
--------
params|default|description
------|-------|-----------
`-o`, `'--output'`|.result/| result output folder 
`-p`, `--period` | 60 * 5| period renew site to download. By default 5 minutes
`--semaphore` | 2 |number of simultaneous connections
`--timeout` |10| timeout in seconds for all. Defaults to 10 seconds.
`--retry` |3| retry connection. Defaults to 3 attempts
`-l`,`--log` | None| locate log file. If none thet print to console
`--debug` | False| Set level to default

Requirements
-----
- python 3.7
- aiohttp
- aiofiles
- beautifulsoup4

Run
---------

For run install requirements
```python
pip isntall -r requirements
```
then run `crawler.py`
```python 
python crawler.py
```