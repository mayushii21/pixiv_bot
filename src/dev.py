import asyncio
import os
import re
import sqlite3
from pathlib import Path

import aiohttp
import orjson
from bs4 import BeautifulSoup

# Create necessary requests.get kwargs
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "referer": "https://www.pixiv.net/",
}

params = {"lang": "en"}
get_kws = {"headers": headers, "params": params}

# Get the absolute path of the directory containing the script
script_directory = Path(__file__).resolve().parent
# Construct the absolute path to the database file
database_path = script_directory / "pixiv_pix.db"
# Construct the absolute path to the blacklist file
blacklist_path = script_directory / "blacklist"

# DB connection
if os.path.exists(database_path):
    con = sqlite3.connect(database_path)
    cur = con.cursor()
else:
    con = sqlite3.connect(database_path)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS artwork (
            id INTEGER PRIMARY KEY NOT NULL,
            status INTEGER NOT NULL
        );
        """
    )
    con.commit()

# Load blacklisted tags
with open(blacklist_path, "r", encoding="utf-8") as f:
    blacklist = {line.rstrip() for line in f}

# Load successfully processed id's
id_set = {
    id[0]
    for id in cur.execute(
        """
        SELECT id
        FROM artwork
        """
    ).fetchall()
}


async def get_top_ranked(session, kws):
    # Request and parse the web page
    async with session.get(
        "https://www.pixiv.net/ranking.php?mode=daily&content=illust",
        headers=kws["headers"],
        params=kws["params"],
    ) as response:
        response_text = await response.text()

    soup = BeautifulSoup(response_text, "lxml")

    # Obtain top 50 id's
    matches = soup.find_all("section", class_="ranking-item")
    ids = {int(item["data-id"]) for item in matches}
    new_ids = ids - id_set

    return new_ids, kws


# # DEAL WITH THIS
# async def get_img(session, img_url, kws):
#     async with session.get(
#         img_url,
#         headers=kws["headers"],
#         params=kws["params"],
#     ) as response:
#         img_bytes = await response.read()
#     # print(img_url[-16:-7])
#     # print(img_bytes)
#     img_extension = img_url.split(".")[-1]
#     with open(f"{img_url[-16:-7]}.{img_extension}", "wb") as file:
#         file.write(img_bytes)
#     return img_bytes


async def get_img_data(session, artwork_id, kws):
    page_url = "https://www.pixiv.net/en/artworks/" + artwork_id

    async with session.get(
        page_url,
        headers=kws["headers"],
        params=kws["params"],
    ) as response:
        response_text = await response.text()

    soup = BeautifulSoup(response_text, "lxml")
    match = soup.find("meta", id="meta-preload-data")

    img_data = orjson.loads(match["content"])["illust"][artwork_id]

    # Check if flagged as sensitive by pixiv
    if img_data["urls"]["original"] is None:
        print(f"nsfw exception {artwork_id}")
        raise Exception(
            "This work cannot be displayed as it may contain sensitive content"
        )

    map_table = str.maketrans(" -+/&", "_____")
    pattern = re.compile(r"\W")
    tags = []
    for tag in img_data["tags"]["tags"]:
        if "translation" in tag and "en" in tag["translation"]:
            tags.append(
                "#" + pattern.sub("", tag["translation"]["en"].translate(map_table))
            )
        elif "romaji" in tag:
            tags.append("#" + pattern.sub("", tag["romaji"].translate(map_table)))
        elif "tag" in tag:
            tags.append("#" + pattern.sub("", tag["tag"].translate(map_table)))

    # Check if any tags are blacklisted
    if set(tags) & blacklist:
        print(f"nsfw tag {artwork_id}")
        raise Exception(
            "This work cannot be displayed as it may contain sensitive content"
        )

    # print(img_data["urls"])

    payload = {
        "title": img_data["title"],
        "page_url": page_url,
        "author": img_data["userName"],
        "author_url": "https://www.pixiv.net/en/users/" + img_data["userId"],
        "tags": " ".join(tags),
        # "img": await get_img(session, img_data["urls"]["original"], kws),
        "img_url": img_data["urls"]["original"],
        # "img_url": img_data["urls"]["regular"],
        "artwork_id": int(artwork_id),
    }
    # print("payload")

    return payload


async def create_payload():
    async with aiohttp.ClientSession() as session:
        ids, kws = await get_top_ranked(session, get_kws)
        payload = []
        nsfw_ids = set()

        async def process_artwork(i, artwork_id):
            try:
                print(f"processing {artwork_id}")
                data = await get_img_data(session, str(artwork_id), get_kws)
                payload.append(data)
            except Exception:
                nsfw_ids.add(artwork_id)

        tasks = [process_artwork(i, artwork_id) for i, artwork_id in enumerate(ids)]
        await asyncio.gather(*tasks)

        sfw_ids = ids - nsfw_ids

    return payload, sfw_ids, nsfw_ids


def populate_w_ids(sfw_ids, nsfw_ids):
    sfw_ids_params = [(id,) for id in sfw_ids]
    cur.executemany(
        """
        INSERT
            OR IGNORE INTO artwork (id, status)
        VALUES (?, 1)
        """,
        sfw_ids_params,
    )
    nsfw_ids_params = [(id,) for id in nsfw_ids]
    cur.executemany(
        """
        INSERT
            OR IGNORE INTO artwork (id, status)
        VALUES (?, 0)
        """,
        nsfw_ids_params,
    )
    con.commit()
    id_set.update(sfw_ids | nsfw_ids)


async def main():
    payload, sfw_ids, nsfw_ids = await create_payload()
    # populate_w_ids(sfw_ids, nsfw_ids)
    return payload


if __name__ == "__main__":
    asyncio.run(main())
