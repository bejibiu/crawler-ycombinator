import argparse
import asyncio
import logging
import os

import aiohttp
import async_timeout

from bs4 import BeautifulSoup

SITE_NEWS = "https://news.ycombinator.com"
NEWS_DETAILS_URL = SITE_NEWS + "/item?id={id_news}"
BASE_DIR = os.path.dirname(__file__)


async def fetch(session, url, is_for_parse=True):
    # TODO: add retry!

        with async_timeout.timeout(50):
            try:
                async with session.get(url) as response:
                    if is_for_parse:
                        news_details = await response.text()
                        soup = BeautifulSoup(news_details, "html.parser")
                        news_site = soup.find("a", {"class": "storylink"})["href"]
                        all_links = [
                            link["href"]
                            for link in soup.find(
                                "table", {"class": "comment-tree"}
                            ).find_all("a")
                            if link["href"].startswith("https://")
                        ]
                        news_text = await fetch(session, news_site, is_for_parse=False)
                        comments_news = [
                            asyncio.create_task(
                                fetch(session, url_from_comment, is_for_parse=False)
                            )
                            for url_from_comment in all_links
                        ]
                        await asyncio.gather(*comments_news)
                        print(comments_news)
                    else:
                        return await response.text()
            except aiohttp.ClientError:
                await asyncio.sleep(0.5)


async def main(args):
    semaphore = asyncio.Semaphore(5)
    async with aiohttp.ClientSession() as session:
        res = await fetch(session, SITE_NEWS, is_for_parse=False)
        soup = BeautifulSoup(res, "html.parser")
        list_tasks_fetch_news = []
        for news in soup.find_all("tr", {"class": "athing"}):
            list_tasks_fetch_news.append(
                asyncio.create_task(
                    fetch(session, NEWS_DETAILS_URL.format(id_news=news["id"]))
                )
            )
        await asyncio.gather(*list_tasks_fetch_news)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(BASE_DIR, "result"),
        help="result output folder",
    )
    parser.add_argument(
        "--timeout",
        action="store",
        default=10,
        type=int,
        help="timeout in seconds for all. Defaults to 10 seconds.",
    )
    parser.add_argument(
        "--retry",
        action="store",
        default=3,
        type=int,
        help="retry connection. Defaults to 3 attempts",
    )
    parser.add_argument("-l", "--log", action="store", default=None)
    parser.add_argument("--debug", action="store_true", default=False)

    args = parser.parse_args()
    logging.basicConfig(
        filename=args.log,
        level=logging.INFO if not args.debug else logging.DEBUG,
        format="[%(asctime)s] %(threadName)s %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )
    asyncio.run(main(args))
