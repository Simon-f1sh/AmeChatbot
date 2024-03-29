import aiosqlite
import sqlite3
import asyncio
import nonebot

driver: nonebot.Driver = nonebot.get_driver()
config: nonebot.config.Config = driver.config


@driver.on_startup
async def init_db():
    config.db = await aiosqlite.connect("src/static/chiyuki.db")
    try:
        await config.db.executescript("create table quiz_table (group_id bigint, enabled bit);")

    except sqlite3.OperationalError:
        print(sqlite3.OperationalError)

    try:
        await config.db.executescript(
            "create table group_poke_table (group_id bigint primary key not null, last_trigger_time int, triggered int, disabled bit, strategy text);")

    except sqlite3.OperationalError:
        print(sqlite3.OperationalError)

    try:
        await config.db.executescript("create table user_poke_table (user_id bigint, group_id bigint, triggered int);")

    except sqlite3.OperationalError:
        print(sqlite3.OperationalError)

    try:
        await config.db.executescript("create table guess_table (group_id bigint, enabled bit);")

    except sqlite3.OperationalError:
        print(sqlite3.OperationalError)


@driver.on_shutdown
async def free_db():
    await config.db.close()
