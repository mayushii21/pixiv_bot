import asyncio
import logging
import os

import dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters.command import Command

# Initialize the logger and load the .env file
logging.basicConfig(level=logging.INFO)
dotenv.load_dotenv()

# Initialize Bot instance
bot = Bot(token=os.getenv("BOT_TOKEN"), parse_mode=ParseMode.HTML)
# # Dispatcher
dp = Dispatcher()


# /start command handler
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.reply(
        "<b><i>B-baka!</i></b> I'm not a tsundere.. <i>What are you, stupid?</i>"
    )


# And the run events dispatching
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
