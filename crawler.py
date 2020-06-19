import argparse
import asyncio
import logging
import os
import re

import aiohttp
import async_timeout

from aiofile import AIOFile
from bs4 import BeautifulSoup

SITE_NEWS = "https://news.ycombinator.com"
# SITE_NEWS = "http://ycombinator.com"
NEWS_DETAILS_URL = SITE_NEWS + "/item?id={id_news}"
# NEWS_DETAILS_URL = SITE_NEWS + "/{id_news}"
BASE_DIR = os.path.dirname(__file__)
RESULT_DIR = os.path.join(BASE_DIR, "output")


async def download_one(session, url, encoded=True):
    try:
        with async_timeout.timeout(10):
            async with session.get(url) as response:
                if encoded:
                    return await response.text()
                return await response.read()
    except asyncio.TimeoutError:
        logging.error(f"url {url} not avalible.")
    except Exception as e:
        logging.error(f"Other error {url}. Error: {e} ")


async def save_text(path_to_save, text):
    if not text:
        logging.error("Not data to  write")
        return None
    if not os.path.exists(os.path.dirname(path_to_save)):
        os.mkdir(os.path.dirname(path_to_save))
    async with AIOFile(path_to_save, "wb") as f:
        await f.write(text)


def slugify(text):
    return re.sub(r'[\W_]+', '-', text)


async def fetch(session, url, semaphore):
    async with semaphore:
        news_details = await download_one(session, url)
        if not news_details:
            logging.error(f"News on site {news_details}, not download")
            return None

        soup = BeautifulSoup(news_details, "html.parser")

        news_name = slugify(soup.find("a", {"class": "storylink"}).text)

        await save_text(
            os.path.join(RESULT_DIR, news_name if news_name else url.split("=")[-1], "news_details.html"),
            news_details.encode(),
        )
        if news_name:
            await download_theme_news(news_name, session, soup)
        await download_link_from_comments(news_name, session, soup)
        logging.info(f"news {news_name} was full download ")


async def download_link_from_comments(news_name, session, soup):
    all_links = []
    comment_tree = soup.find("table", {"class": "comment-tree"})
    if soup.find("table", {"class": "comment-tree"}):
        all_links = [
            link["href"]
            for link in comment_tree.find_all("a")
            if link["href"].startswith("https://")
        ]
    logging.info(f"Found {len(all_links)} comment for news {news_name}")

    comments_news = [
        asyncio.create_task(download_one(session, url_from_comment, encoded=False))
        for url_from_comment in all_links
    ]
    comments_list_text = await asyncio.gather(*comments_news)
    for num, i in enumerate(comments_list_text):
        if i:
            await save_text(os.path.join(RESULT_DIR, news_name, f"comment{num}"), i)


async def download_theme_news(news_name, session, soup):
    news_site_block = soup.find("a", {"class": "storylink"})
    news_site = news_site_block["href"]
    news_text = await download_one(session, news_site, encoded=False)
    if not news_text:
        logging.error(f"url {news_site} not avalible.")
        news_text = f"Sorry =(. Url {news_site} not avalible.".encode()
    await save_text(os.path.join(RESULT_DIR, news_name, news_name), news_text)


async def main(args, list_news):
    semaphore = asyncio.Semaphore(2)
    async with aiohttp.ClientSession() as session:
        res = await download_one(session, SITE_NEWS)
        soup = BeautifulSoup(res, "html.parser")
        list_tasks_fetch_news = []
        for news in soup.find_all("tr", {"class": "athing"}):
            if news["id"] in list_news:
                logging.debug(f"news '{news.text}' already download")
                continue
            list_news.append(news["id"])
            logging.info(f"News '{news.text.strip()}' add to fetching")
            list_tasks_fetch_news.append(
                asyncio.create_task(
                    fetch(
                        session, NEWS_DETAILS_URL.format(id_news=news["id"]), semaphore
                    )
                )
            )
        await asyncio.gather(*list_tasks_fetch_news)
    print("This all")


async def run_forever(args, list_news):
    while True:
        logging.info("Run chiclefetche news")
        await main(args, list_news)
        await asyncio.sleep(args.period)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(BASE_DIR, "result"),
        help="result output folder",
    )
    parser.add_argument(
        "-p", "--period", default=60 * 5, type=int,
        help="period renew site to download",
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
    if not os.path.exists(RESULT_DIR):
        os.mkdir(RESULT_DIR)
    list_news = []
    asyncio.run(run_forever(args, list_news))
