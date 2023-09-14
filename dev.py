import json
import os
import sqlite3

import requests
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


def get_top_ranked(kws):
    # Request and parse the web page
    r = requests.get(
        "https://www.pixiv.net/ranking.php?mode=daily&content=illust", **kws
    )
    soup = BeautifulSoup(r.text, "lxml")

    # Obtain top 50 id's
    matches = soup.find_all("section", class_="ranking-item")
    ids = {item["data-id"] for item in matches}
    new_ids = ids - id_set

    return new_ids, kws


def create_payload(ids, kws):
    payload = []
    nsfw_ids = set()
    for i, id in enumerate(ids):
        print(i)
        # Skip sensitive (nsfw) content
        try:
            data = get_img_data(id, kws)
            if data["tags"] & blacklist:
                nsfw_ids.add(id)
                print("nsfw tag")
                continue
            payload.append(data)
        except Exception:
            print("nsfw exception")
            nsfw_ids.add(id)
            continue
    return payload, ids, nsfw_ids


def get_img_data(id, kws):
    r = requests.get("https://www.pixiv.net/en/artworks/" + id, **kws)
    soup = BeautifulSoup(r.text, "lxml")

    match = soup.find("meta", id="meta-preload-data")

    img_data = json.loads(match["content"])["illust"][id]

    tags = set()
    for tag in img_data["tags"]["tags"]:
        if "translation" in tag and "en" in tag["translation"]:
            tags.add(
                "#"
                + tag["translation"]["en"].translate(str.maketrans(" .-()", "_____"))
            )
        elif "romaji" in tag:
            tags.add("#" + tag["romaji"].translate(str.maketrans(" .-()", "_____")))
        elif "tag" in tag:
            tags.add("#" + tag["tag"].translate(str.maketrans(" .-()", "_____")))

    payload = {
        "artwork_id": id,
        "title": img_data["title"],
        "author": img_data["userName"],
        "author_id": img_data["userId"],
        "tags": tags,
    }

    # img_url = img_data['urls']['original']
    #    img_extension = img_url.split('.')[-1]
    #
    #    r = requests.get(img_url, **kws)
    #
    #    with open(f'{id}.{img_extension}', 'wb') as file:
    #        file.write(r.content)

    return payload


def send_payload(payload, ids, nsfw_ids):
    print(payload)
    populate_w_ids(ids, nsfw_ids)


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


send_payload(*create_payload(*get_top_ranked(get_kws)))

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