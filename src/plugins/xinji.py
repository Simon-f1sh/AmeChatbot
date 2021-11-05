import re
import os
import pytz

from nonebot import require, on_command, on_regex, get_driver, logger, get_bots
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Message, Event, Bot, MessageSegment, GROUP_ADMIN, GROUP_OWNER, GroupMessageEvent

from collections import defaultdict

from datetime import datetime, timedelta

driver = get_driver()

SH = pytz.timezone('Asia/Shanghai')
scheduler = require("nonebot_plugin_apscheduler").scheduler

counter = 0
otw_counter = 0
curr_time = ""
otw_dict = defaultdict(int)
open_time = datetime.now(SH).replace(hour=7, minute=0, second=0, microsecond=0)


async def clear_counter():
    global open_time
    open_time += timedelta(days=1)
    logger.info(open_time)
    xinji_clear()
    (bot,) = get_bots().values()
    await bot.send_group_msg(group_id=879106299, message="机厅已关门，新几数据已清空")
    await bot.send_group_msg(group_id=879106299, message="新几相关功能已关闭，将于次日7点重新开启")


@driver.on_startup
def _():
    global open_time
    if datetime.now(SH) >= datetime.now(SH).replace(hour=22, minute=0, second=0, microsecond=0):
        open_time += timedelta(days=1)
    logger.info("Open Time:")
    logger.info(open_time)
    logger.info("Load help text successfully")
    help_text: dict = get_driver().config.help_text
    help_text['xinji'] = ('查看新几相关功能', """19岁，是妹妹。
可用命令如下：
新几    查询新奥目前人数和路上人数
@tpz妹妹 新<人数>    更新新奥目前人数
@tpz妹妹 新[+/-]<人数>    通过加减方式更新人数
@tpz妹妹 路上    将自己的状态设置为“路上”并加入路上人数计数
@tpz妹妹 路上<人数>    组团上路（？
@tpz妹妹 不出了    状态为“路上”才可以使用，鸽了（
@tpz妹妹 到达    状态为“路上”才可以使用，解除“路上”状态并自动更新新奥人数
@tpz妹妹 路上有谁    字面意思""")
    scheduler.add_job(
        clear_counter,
        trigger='cron',
        hour=22,
        minute=0,
    )


xinji = on_regex(r"^(新几)$", block=True)


@xinji.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if curr_time == "":
        await xinji.send(Message([{
            "type": "image",
            "data": {
                "file": "file:///" + os.path.abspath("src/static/mai/xinji/bzd.jpg")
            }
        }]))
    else:
        if counter > 9:
            await xinji.send(Message([{
                "type": "image",
                "data": {
                    "file": "file:///" + os.path.abspath("src/static/mai/xinji/10+.jpg")
                }
            }, MessageSegment.text("\n路上人数: " + str(otw_counter) + "\n更新时间: " + curr_time)]))
        else:
            await xinji.send(Message([{
                "type": "image",
                "data": {
                    "file": "file:///" + os.path.abspath("src/static/mai/xinji/" + str(counter) + ".jpg")
                }
            }, MessageSegment.text("\n路上人数: " + str(otw_counter) + "\n更新时间: " + curr_time)]))


xin_add_minus = on_regex(r"^新(\+|-)([0-9]+)$", rule=to_me(), block=True)


@xin_add_minus.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    global counter
    global curr_time
    now = datetime.now(SH)
    if now < open_time:
        return
    regex = r"新(\+|-)([0-9]+)"
    res = re.match(regex, str(event.get_message()).lower())
    try:
        if res.group(1) == "+":
            counter += int(res.group(2))
            curr_time = now.strftime('%Y/%m/%d %H:%M:%S')
            if counter > 9:
                await xin_add_minus.send(Message([MessageSegment.text("收到"), {
                    "type": "image",
                    "data": {
                        "file": "file:///" + os.path.abspath("src/static/mai/xinji/10+.jpg")
                    }
                }]))
            else:
                await xin_add_minus.send(Message([MessageSegment.text("收到"), {
                    "type": "image",
                    "data": {
                        "file": "file:///" + os.path.abspath("src/static/mai/xinji/" + str(counter) + ".jpg")
                    }
                }]))
        elif res.group(1) == "-":
            if int(res.group(2)) <= counter:
                counter -= int(res.group(2))
                curr_time = now.strftime('%Y/%m/%d %H:%M:%S')
                if counter > 9:
                    await xin_add_minus.send(Message([MessageSegment.text("收到"), {
                        "type": "image",
                        "data": {
                            "file": "file:///" + os.path.abspath("src/static/mai/xinji/10+.jpg")
                        }
                    }]))
                else:
                    await xin_add_minus.send(Message([MessageSegment.text("收到"), {
                        "type": "image",
                        "data": {
                            "file": "file:///" + os.path.abspath("src/static/mai/xinji/" + str(counter) + ".jpg")
                        }
                    }]))
            else:
                await xin_add_minus.send("人数不能为负")
    except Exception as e:
        print("Exception" + str(e))
        await xin_add_minus.finish("命令错误，请检查语法")


xin_number = on_regex(r"^新([0-9]+)$", rule=to_me(), block=True)


@xin_number.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    global counter
    global curr_time
    now = datetime.now(SH)
    if now < open_time:
        return
    regex = r"新([0-9]+)"
    res = re.match(regex, str(event.get_message()).lower())
    try:
        if int(res.group(1)) >= 0:
            counter = int(res.group(1))
            curr_time = now.strftime('%Y/%m/%d %H:%M:%S')
            await xin_number.send("收到")
        else:
            await xin_number.send("人数不能为负")
    except Exception as e:
        print("Exception" + str(e))
        await xin_number.finish("命令错误，请检查语法")


otw = on_regex(r"^路上([0-9]*)$", rule=to_me(), block=True)


@otw.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    global otw_counter
    global curr_time
    now = datetime.now(SH)
    if now < open_time:
        return
    regex = r"路上([0-9]*)"
    res = re.match(regex, str(event.get_message()).lower())
    num = 1
    try:
        if res.group(1) != "":
            num = int(res.group(1))
    except Exception as e:
        print("Exception" + e)
        await otw.finish("命令错误，请检查语法")

    if num > 4:
        await otw.send("面包人？")
        return

    if otw_dict[event.get_user_id()] == num and num != 0:
        await otw.send("以防您脑子不太好用我这边提醒您一下")
        await otw.send("您已经在路上了")
    else:
        otw_counter += num - otw_dict[event.get_user_id()]
        if num == 0:
            otw_dict.pop(event.get_user_id())
        else:
            otw_dict[event.get_user_id()] = num
        curr_time = now.strftime('%Y/%m/%d %H:%M:%S')
        await otw.send("收到，现在路上" + str(otw_counter) + "人")


arrive = on_regex(r"^到达$", rule=to_me(), block=True)


@arrive.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    global otw_counter
    global counter
    global curr_time
    now = datetime.now(SH)
    if now < open_time:
        return
    if otw_dict[event.get_user_id()] == 0:
        otw_dict.pop(event.get_user_id())
        return
    otw_counter -= otw_dict[event.get_user_id()]
    counter += otw_dict[event.get_user_id()]
    otw_dict.pop(event.get_user_id())
    curr_time = now.strftime('%Y/%m/%d %H:%M:%S')
    if counter > 9:
        await arrive.send(Message([MessageSegment.text("收到"), {
            "type": "image",
            "data": {
                "file": "file:///" + os.path.abspath("src/static/mai/xinji/10+.jpg")
            }
        }]))
    else:
        await arrive.send(Message([MessageSegment.text("收到"), {
            "type": "image",
            "data": {
                "file": "file:///" + os.path.abspath("src/static/mai/xinji/" + str(counter) + ".jpg")
            }
        }]))


otw_cancel = on_regex(r"^不出了$", rule=to_me(), block=True)


@otw_cancel.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    global otw_counter
    global curr_time
    now = datetime.now(SH)
    if now < open_time:
        return
    if otw_dict[event.get_user_id()] == 0:
        otw_dict.pop(event.get_user_id())
        return
    otw_counter -= otw_dict[event.get_user_id()]
    otw_dict.pop(event.get_user_id())
    curr_time = now.strftime('%Y/%m/%d %H:%M:%S')
    await otw.send("收到，现在路上" + str(otw_counter) + "人")


otw_who = on_regex(r"^路上有谁$", rule=to_me(), block=True)


@otw_who.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if otw_counter == 0:
        await otw_who.finish("路上没人")
        return
    reply = MessageSegment.text("路上\n")
    for k, v in otw_dict.items():
        reply += MessageSegment.at(k)
        reply += MessageSegment.text(f"\t{v}人\n")
    await otw_who.finish(reply)


clear = on_regex(r"^clear xinji$", permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER, rule=to_me(), block=True)


def xinji_clear():
    global counter, otw_counter, curr_time
    counter = 0
    otw_counter = 0
    curr_time = ""
    otw_dict.clear()


@clear.handle()
async def _(bot: Bot, event: Event, state: T_State):
    xinji_clear()
    await clear.finish("收到")
