import asyncio
import json
import os
import re
import sqlite3

import aiohttp
from bs4 import BeautifulSoup

# Create necessary requests.get kwargs
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "referer": "https://www.pixiv.net/",
}
params = {"lang": "en"}
get_kws = {"headers": headers, "params": params}

# DB connection
if os.path.exists("pixiv_pix.db"):
    con = sqlite3.connect("pixiv_pix.db")
    cur = con.cursor()
else:
    con = sqlite3.connect("pixiv_pix.db")
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
with open("blacklist.txt", "r", encoding="utf-8") as f:
    blacklist = {line.rstrip() for line in f}

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


async def get_img_data(session, artwork_id, kws):
    print("loading")

    async with session.get(
        "https://www.pixiv.net/en/artworks/" + artwork_id,
        headers=kws["headers"],
        params=kws["params"],
    ) as response:
        response_text = await response.text()

    print("loaded, parsing")

    soup = BeautifulSoup(response_text, "lxml")
    match = soup.find("meta", id="meta-preload-data")

    print("parsed, accessing")

    img_data = json.loads(match["content"])["illust"][artwork_id]

    print("accessed")

    map_table = str.maketrans(" -+/&", "_____")
    pattern = re.compile(r"\W")
    tags = set()
    for tag in img_data["tags"]["tags"]:
        if "translation" in tag and "en" in tag["translation"]:
            tags.add(
                "#" + pattern.sub("", tag["translation"]["en"].translate(map_table))
            )
        elif "romaji" in tag:
            tags.add("#" + pattern.sub("", tag["romaji"].translate(map_table)))
        elif "tag" in tag:
            tags.add("#" + pattern.sub("", tag["tag"].translate(map_table)))

    payload = {
        "artwork_id": artwork_id,
        "title": img_data["title"],
        "author": img_data["userName"],
        "author_id": img_data["userId"],
        "tags": tags,
    }

    print("payload")

    # img_url = img_data['urls']['original']
    #    img_extension = img_url.split('.')[-1]
    #
    #    r = requests.get(img_url, **kws)
    #
    #    with open(f'{id}.{img_extension}', 'wb') as file:
    #        file.write(r.content)

    return payload


# async def create_payload(kws):
#     async with aiohttp.ClientSession() as session:
#         ids, kws = await get_top_ranked(session, kws)
#         payload = []
#         nsfw_ids = set()
#         for i, artwork_id in enumerate(ids):
#             print(i)
#             # Skip sensitive (nsfw) content
#             try:
#                 data = await get_img_data(session, str(artwork_id), kws)
#                 if data["tags"] & blacklist:
#                     nsfw_ids.add(artwork_id)
#                     print("nsfw tag")
#                     continue
#                 payload.append(data)
#             except Exception:
#                 print("nsfw exception")
#                 nsfw_ids.add(artwork_id)
#                 continue
#     return payload, ids, nsfw_ids


async def create_payload(kws):
    async with aiohttp.ClientSession() as session:
        ids, kws = await get_top_ranked(session, kws)
        payload = []
        nsfw_ids = set()

        async def process_artwork(i, artwork_id):
            try:
                print(f"{i}")
                data = await get_img_data(session, str(artwork_id), kws)
                if data["tags"] & blacklist:
                    nsfw_ids.add(artwork_id)
                    print("nsfw tag")
                else:
                    payload.append(data)
                    print(f"appended {i}")
            except Exception:
                print(f"nsfw exception {artwork_id}")
                nsfw_ids.add(artwork_id)

        tasks = {process_artwork(i, artwork_id) for i, artwork_id in enumerate(ids)}
        await asyncio.gather(*tasks)

    return payload, ids, nsfw_ids


def populate_w_ids(total_new_ids, nsfw_ids):
    ids_params = [(id,) for id in total_new_ids - nsfw_ids]
    cur.executemany(
        """
        INSERT
            OR IGNORE INTO artwork (id, status)
        VALUES (?, 1)
        """,
        ids_params,
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
    id_set.update(total_new_ids)


async def send_payload():
    payload, ids, nsfw_ids = await create_payload(get_kws)
    print(payload)
    populate_w_ids(ids, nsfw_ids)
    return payload


# tags_url = 'https://www.pixiv.net/en/artworks/111620869'

# r = requests.get(tags_url, **kws)
# soup = BeautifulSoup(r.text, 'lxml')

# match = soup.find('meta', id='meta-preload-data')
#
# img_data = json.loads(match['content'])['illust']['111620869']

# print(img_data)

# tags = []
# for tag in img_data['tags']['tags']:
#    if 'translation' in tag and 'en' in tag['translation']:
#        tags.append('#' + tag['translation']['en'].replace(' ', '_'))
#    elif 'romaji' in tag:
#        tags.append('#' + tag['romaji'].replace(' ', '_'))
#    elif 'tag' in tag:
#        tags.append('#' + tag['tag'].replace(' ', '_'))

# print(tags)

if __name__ == "__main__":
    asyncio.run(send_payload())
