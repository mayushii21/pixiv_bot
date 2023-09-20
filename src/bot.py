import asyncio
import logging
import os

import dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.command import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from background import keep_alive
from dev import create_payload, populate_w_ids

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


async def send_artwork(item, url):
    await bot.send_photo(
        CHANNEL_ID,
        photo=url,
        caption=f"<a href='{item['page_url']}'>{item['title']}</a>\nAuthor: <a href='{item['author_url']}'>{item['author']}</a>\nTags: {item['tags']}",
    )
    await bot.send_document(CHANNEL_ID, document=url)


# /get command in case cron fails
@dp.message(Command("get"))
async def send_payload(message: types.Message):
    await bot.send_message(ADMIN_ID, "Updating...")
    payload, new_sfw_ids, nsfw_ids = await create_payload()
    sent_sfw_ids = set()
    tries = 0
    while new_sfw_ids and tries < 3:
        for item in payload:
            # Skip already sent artworks
            if item["artwork_id"] in sent_sfw_ids:
                continue
            url = item["img_url"]
            try:
                await send_artwork(item, url)
                sent_sfw_ids.add(item["artwork_id"])
                # Flood control prevention
                await asyncio.sleep(6)
            except TelegramBadRequest:
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
    # Schedule the send_payload function to run daily at 13:20-13:35 (GMT+9)
    scheduler.add_job(
        send_payload,
        "cron",
        hour=13,
        minute=20,
        second=0,
        timezone="Asia/Tokyo",  # Set the timezone to GMT+9 (Asia/Tokyo)
        args=(None,),
    )
    scheduler.add_job(
        send_payload,
        "cron",
        hour=13,
        minute=25,
        second=0,
        timezone="Asia/Tokyo",  # Set the timezone to GMT+9 (Asia/Tokyo)
        args=(None,),
    )
    scheduler.add_job(
        send_payload,
        "cron",
        hour=13,
        minute=30,
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
