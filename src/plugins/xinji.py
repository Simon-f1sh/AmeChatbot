import re

from nonebot import require, on_command, on_regex
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters import Event, Bot

scheduler = require("nonebot_plugin_apscheduler").scheduler

counter = 0

xinji = on_regex(r"^(新几)$", block=True)


@xinji.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if counter > 99:
        await xinji.send("🆕1⃣️🥣")
    else:
        await xinji.send("新" + str(counter))


xin_add_minus = on_regex(r"^新(\+|-)([0-9]+)$", rule=to_me(), block=True)


@xin_add_minus.handle()
async def _(bot: Bot, event: Event, state: T_State):
    global counter
    regex = r"新(\+|-)([0-9]+)"
    res = re.match(regex, str(event.get_message()).lower())
    try:
        if res.group(1) == "+":
            counter += int(res.group(2))
            await xin_add_minus.send("收到")
        elif res.group(1) == "-":
            if int(res.group(2)) <= counter:
                counter -= int(res.group(2))
                await xin_add_minus.send("收到")
            else:
                await xin_add_minus.send("人数不能为负")
    except Exception as e:
        print("Exception" + e)
        await xin_add_minus.finish("命令错误，请检查语法")


xin_number = on_regex(r"^新([0-9]+)$", rule=to_me(), block=True)


@xin_number.handle()
async def _(bot: Bot, event: Event, state: T_State):
    global counter
    regex = r"新([0-9]+)"
    res = re.match(regex, str(event.get_message()).lower())
    try:
        if int(res.group(1)) >= 0:
            counter = int(res.group(1))
            await xin_number.send("收到")
        else:
            await xin_number.send("人数不能为负")
    except Exception as e:
        print("Exception" + e)
        await xin_number.finish("命令错误，请检查语法")

