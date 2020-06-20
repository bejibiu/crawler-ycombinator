import argparse
import asyncio
import logging
import os
import re
import string
import random

import aiohttp

import aiofiles
from bs4 import BeautifulSoup

SITE_NEWS = "https://news.ycombinator.com"
NEWS_DETAILS_URL = SITE_NEWS + "/item?id={id_news}"
BASE_DIR = os.path.dirname(__file__)


async def download_one(session, url):
    try:
        async with session.get(url) as response:
            return await response.read(), response.url
    except asyncio.TimeoutError:
        logging.error(f"url {url} not avalible.")
    except Exception as e:
        logging.error(f"Other error {url}. Error: {e} ")


async def save_to_file(path_to_save, data):
    if not data:
        logging.error(f"Not data to  write to file by path {path_to_save}")
        return None
    if not os.path.exists(os.path.dirname(path_to_save)):
        os.mkdir(os.path.dirname(path_to_save))
    if os.path.exists(path_to_save):
        logging.debug("File exist. Change name")
        path_to_save += "".join(random.choice(string.ascii_lowercase) for i in range(5))
    try:
        async with aiofiles.open(path_to_save, mode="wb") as f:
            await f.write(data)
    except OSError as e:
        logging.error(f"File with path: {path_to_save} can not save. Error: {e}")


def slugify(text):
    return re.sub(r"[^a-zA-Z0-9 .]+", "-", text)


async def fetch(output_folder, session, url, semaphore):
    async with semaphore:
        news_details, _ = await download_one(session, url)
        if not news_details:
            logging.error(f"News on site {news_details}, not download")
            return None
        soup = BeautifulSoup(news_details, "html.parser")

        news_name = slugify(soup.find("a", {"class": "storylink"}).text)

        await save_to_file(
            os.path.join(
                output_folder,
                news_name if news_name else url.split("=")[-1],
                "news_details.html",
            ),
            news_details,
        )
        if news_name:
            await download_theme_news(output_folder, news_name, session, soup)
        await download_link_from_comments(output_folder, news_name, session, soup)
        logging.info(f"news {news_name} was full download ")


async def download_link_from_comments(output_folder, news_name, session, soup):
    all_links = []
    comment_tree = soup.find("table", {"class": "comment-tree"})
    if soup.find("table", {"class": "comment-tree"}):
        all_links = [
            link["href"]
            for link in comment_tree.find_all("a")
            if link["href"].startswith("https://") or link["href"].startswith("http://")
        ]
    logging.info(f"Found {len(all_links)} comment for news {news_name}")

    comments_news = [
        asyncio.create_task(download_one(session, url_from_comment))
        for url_from_comment in all_links
    ]
    comments_list_tuple = await asyncio.gather(*comments_news)
    for num, comment_with_url in enumerate(comments_list_tuple):
        if comment_with_url:
            name_file = (
                comment_with_url[1].name
                if comment_with_url[1].name
                else slugify(str(comment_with_url[1]))
            )
            await save_to_file(
                os.path.join(output_folder, news_name, name_file), comment_with_url[0]
            )


async def download_theme_news(output_folder, news_name, session, soup):
    news_site_block = soup.find("a", {"class": "storylink"})
    news_site = news_site_block["href"]
    if not news_site.startswith("https://") and not news_site.startswith("http://"):
        logging.info("News text locate in details")
        return None
    news_theme = await download_one(session, news_site)
    if not news_theme:
        logging.error(f"url {news_site} not avalible.")
        news_theme[0] = f"Sorry =(. Url {news_site} not avalible.".encode()
    await save_to_file(os.path.join(output_folder, news_name, news_name), news_theme[0])


async def main(args, list_news):
    semaphore = asyncio.Semaphore(args.semaphore)
    timeout = aiohttp.ClientTimeout(total=args.timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        res, _ = await download_one(session, SITE_NEWS)
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
                        args.output,
                        session,
                        NEWS_DETAILS_URL.format(id_news=news["id"]),
                        semaphore,
                    )
                )
            )
        await asyncio.gather(*list_tasks_fetch_news)
    logging.info("Fetch all.")


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
        default=os.path.join(BASE_DIR, "output"),
        help="result output folder",
    )
    parser.add_argument(
        "-p",
        "--period",
        default=60 * 5,
        type=int,
        help="period renew site to download",
    )
    parser.add_argument(
        "--semaphore", default=2, type=int, help="number of simultaneous connections",
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
    if not os.path.exists(args.output):
        os.mkdir(args.output)
    list_news = []
    asyncio.run(run_forever(args, list_news))
