import asyncio
import logging
import os

import dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters.command import Command
from aiogram.types import URLInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from background import keep_alive
from dev import create_payload, headers, populate_w_ids

# Initialize the logger and load the .env file
logging.basicConfig(level=logging.INFO)
dotenv.load_dotenv()

# Initialize Bot instance
bot = Bot(token=os.getenv("BOT_TOKEN"), parse_mode=ParseMode.HTML)
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
# Dispatcher
dp = Dispatcher()

# Create a scheduler instance
scheduler = AsyncIOScheduler()


# /start command handler
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply(
        "<b><i>B-baka!</i></b> I'm not a tsundere.. <i>What are you, stupid?</i>"
    )


async def upload_artwork(item, url):
    try:
        extension = url.split(".")[-1]
        image = URLInputFile(
            url,
            filename=f"{item['artwork_id']}.{extension}",
            headers=headers,
            timeout=60,
        )
    except (TelegramBadRequest, TelegramNetworkError) as e:
        print(f"Error uploading: {e}")

    return (item, image)


async def send_artwork(item, image):
    await bot.send_photo(
        CHANNEL_ID,
        photo=image,
        caption=f"<a href='{item['page_url']}'>{item['title']}</a>\nAuthor: <a href='{item['author_url']}'>{item['author']}</a>\nTags: {item['tags']}",
    )
    await bot.send_document(
        CHANNEL_ID,
        document=image,
    )


# /get command in case cron fails
@dp.message(Command("get"))
async def send_payload(message: types.Message):
    await bot.send_message(ADMIN_ID, "Updating...")
    payload, new_sfw_ids, nsfw_ids = await create_payload()
    sent_sfw_ids = set()
    tries = 0
    while new_sfw_ids and tries < 2:
        # Upload artworks while skipping already sent ones
        print()
        tasks = [
            upload_artwork(art, art["img_url"])
            for art in payload
            if art["artwork_id"] not in sent_sfw_ids
        ]
        artworks = await asyncio.gather(*tasks)
        for art in artworks:
            try:
                await send_artwork(art[0], art[1])
                sent_sfw_ids.add(art[0]["artwork_id"])
                # Flood control prevention
                await asyncio.sleep(6)
            except (TelegramBadRequest, TelegramNetworkError) as e:
                print(f"Error sending: {e}")
                await asyncio.sleep(3)
        tries += 1
        new_sfw_ids.difference_update(sent_sfw_ids)
        # Wait between retries
        await asyncio.sleep(10)
    # Populate db and update set with processed id's
    populate_w_ids(sent_sfw_ids, nsfw_ids)
    await bot.send_message(
        ADMIN_ID, f"Successfully sent: {sent_sfw_ids}\nFailed to send: {new_sfw_ids}"
    )


async def main():
    # Schedule the send_payload function to run daily at 13:15 & 13:35 (GMT+9)
    scheduler.add_job(
        send_payload,
        "cron",
        hour=13,
        minute=15,
        second=0,
        timezone="Asia/Tokyo",  # Set the timezone to GMT+9 (Asia/Tokyo)
        args=(None,),
    )
    scheduler.add_job(
        send_payload,
        "cron",
        hour=13,
        minute=35,
        second=0,
        timezone="Asia/Tokyo",  # Set the timezone to GMT+9 (Asia/Tokyo)
        args=(None,),
    )
    # Start the scheduler
    scheduler.start()

    # Start the events dispatcher
    await dp.start_polling(bot)


if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
