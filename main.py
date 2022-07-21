
import discord
import os
from dotenv import load_dotenv
import os
import logging
import asyncio
import botconfig
from discord.ext import commands


async def main():
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger('discord')
    logger.setLevel(logging.WARNING)
    handler = logging.FileHandler(
        filename='discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter(
        '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

    os.chdir("/home/pi/betabot")  # very important tbh
    load_dotenv()

    tk = os.getenv("token")
    if tk is None:
        return print("'token' is missing in the .env file")
    bot= botconfig.AndreiBot(activity=discord.Activity(type=discord.ActivityType.listening,
                                              name=os.getenv("status_description")))
    
    await asyncio.sleep(5)
    
    await bot.start(tk, reconnect=True)


if __name__ == "__main__":
    asyncio.run(main())
