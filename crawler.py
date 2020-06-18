import argparse
import asyncio
import logging
import os

import aiohttp
import async_timeout

from aiofile import AIOFile
from bs4 import BeautifulSoup

SITE_NEWS = "https://news.ycombinator.com"
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
    except (aiohttp.client_exceptions.ClientConnectionError, UnicodeDecodeError,) as e:
        logging.error(f"can not load {url}. Error = {e}")
    except asyncio.exceptions.TimeoutError:
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


async def fetch(session, url, semaphore):
    async with semaphore:
        news_details = await download_one(session, url)
        if not news_details:
            logging.error(f"News on site {news_details}, not download")
            return None
        soup = BeautifulSoup(news_details, "html.parser")
        news_site_block = soup.find("a", {"class": "storylink"})
        if not news_site_block:
            logging.error(f"Not found site for this news: {url}")
        news_site = news_site_block["href"]
        news_name = news_site_block.text.translate(
            str.maketrans("\_-/:$!@#$", "          ")
        )
        await save_text(
            os.path.join(RESULT_DIR, news_name, "news_details.html"),
            news_details.encode(),
        )
        all_links = []
        commnet_tree = soup.find("table", {"class": "comment-tree"})
        if soup.find("table", {"class": "comment-tree"}):
            all_links = [
                link["href"]
                for link in commnet_tree.find_all("a")
                if link["href"].startswith("https://")
            ]
        logging.info(f"Found {len(all_links)} comment for news {news_name}")
        try:
            news_text = await download_one(session, news_site, encoded=False)
        except asyncio.exceptions.TimeoutError:
            logging.error(f"url {news_site} not avalible.")
            news_text = f"Sorry =(. Url {news_site} not avalible.".encode()
        await save_text(os.path.join(RESULT_DIR, news_name, news_name), news_text)
        comments_news = [
            asyncio.create_task(download_one(session, url_from_comment, encoded=False))
            for url_from_comment in all_links
        ]
        comments_list_text = await asyncio.gather(*comments_news)
        for num, i in enumerate(comments_list_text):
            if i:
                await save_text(os.path.join(RESULT_DIR, news_name, f"comment{num}"), i)
        logging.info(f"news {news_name} was full download ")


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(BASE_DIR, "result"),
        help="result output folder",
    )
    parser.add_argument(
        "-p", "--period", default=60 * 5, help="period renew site to download",
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
    import datetime

    now = datetime.datetime.now()
    list_news = []
    # while True:
    asyncio.run(main(args, list_news))
    # import time; time.sleep(3)
    print(datetime.datetime.now() - now)
