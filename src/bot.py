import asyncio
import logging
import os

import dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.command import Command

from dev import create_payload, populate_w_ids

# Initialize the logger and load the .env file
logging.basicConfig(level=logging.INFO)
dotenv.load_dotenv()

# Initialize Bot instance
bot = Bot(token=os.getenv("BOT_TOKEN"), parse_mode=ParseMode.HTML)
# Dispatcher
dp = Dispatcher()


# /start command handler
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply(
        "<b><i>B-baka!</i></b> I'm not a tsundere.. <i>What are you, stupid?</i>"
    )


# /get command
@dp.message(Command("get"))
async def send_payload(message: types.Message):
    payload, new_sfw_ids, nsfw_ids = await create_payload()
    sent_sfw_ids = set()
    tries = 0
    while new_sfw_ids and tries < 3:
        for item in payload:
            if item["artwork_id"] in sent_sfw_ids:
                continue
            url = item["img_url"]
            try:
                await message.answer_photo(
                    photo=url,
                    caption=f"<a href='{item['page_url']}'>{item['title']}</a>\nAuthor: <a href='{item['author_url']}'>{item['author']}</a>\nTags: {item['tags']}",
                )
                await message.answer_document(document=url)
                sent_sfw_ids.add(item["artwork_id"])
            except TelegramBadRequest:
                pass
        tries += 1
        new_sfw_ids.difference_update(sent_sfw_ids)

    populate_w_ids(sent_sfw_ids, nsfw_ids)


async def main():
    # Start the events dispatcher
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
