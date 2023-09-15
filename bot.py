import asyncio
import logging
import os

import dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters.command import Command

from dev import send_payload

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
async def get_top_ranked(message: types.Message):
    for item in await send_payload():
        url = item["img_url"]
        await message.answer_photo(
            photo=url,
            caption=f"<a href='{item['page_url']}'>{item['title']}</a>\nAuthor: <a href='{item['author_url']}'>{item['author']}</a>\nTags: {item['tags']}",
        )
        await message.answer_document(document=url)


async def main():
    # Start the events dispatcher
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
