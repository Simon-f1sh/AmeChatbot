import math
from collections import defaultdict
from typing import List, Dict, Any

from dotenv import load_dotenv
from nonebot import on_command, on_message, on_notice, on_regex, get_driver, require, get_bots
from nonebot.log import logger
from nonebot.permission import Permission
from nonebot.typing import T_State
from nonebot.adapters import Event, Bot
from nonebot.adapters.cqhttp import Message, MessageSegment, GroupMessageEvent, PrivateMessageEvent
from src.libraries.maimaidx_guess import GuessObject

from qcloud_cos import CosConfig, CosS3Client
from sts.sts import Sts

from PIL import Image
from src.libraries.image import image_to_base64
from src.libraries.tool import hash
from src.libraries.maimaidx_music import *
from src.libraries.image import *
from src.libraries.maimai_best_40 import generate, analyze
from src.libraries.maimai_records import get_records_by_level
import requests
import json
import random
import time
import re
import os
import shelve
import asyncio
from urllib import parse

# 配置腾讯api

load_dotenv()
secret_id = os.getenv('SECRET_ID')  # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.getenv('SECRET_KEY')  # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-beijing'  # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
bucket_name = "tpz-1254072339"
config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
client = CosS3Client(config)

driver = get_driver()

scheduler = require("nonebot_plugin_apscheduler").scheduler


async def sandian():
    (bot,) = get_bots().values()
    await bot.send_group_msg(group_id=879106299, message=MessageSegment.image(
        "file:///" + os.path.abspath("src/static/mai/pic/sandian.jpg")))


@driver.on_startup
def _():
    logger.info("Load help text successfully")
    help_text: dict = get_driver().config.help_text
    help_text['mai'] = ('查看舞萌相关功能', """19岁，是妹妹。
可用命令如下：
今日运势 查看今天的舞萌运势
XXXmaimaiXXX什么 随机一首歌
随个[dx/标准][绿黄红紫白]<难度> 随机一首指定条件的乐曲
search<乐曲标题的一部分> 查询符合条件的乐曲
[绿黄红紫白]id <歌曲编号> 查询乐曲信息或谱面信息
<歌曲别名>是啥歌 查询乐曲别名对应的乐曲
base <定数>  查询定数对应的乐曲
base <定数下限> <定数上限>
line <难度+歌曲id> <分数线> 详情请输入“line 帮助”查看
妹妹猜歌 猜歌游戏
<随机数量>底分分析<查分器id> 通过b40情况推荐推分歌曲 <随机数量>和<查分器id>可不填
妹妹唱歌 <歌曲id> 根据id点歌，不填写id时为随机点歌
妹妹唱<歌曲名称/别名> 根据名称或别名点歌""")
    scheduler.add_job(
        sandian,
        trigger='cron',
        hour=15,
        minute=0,
    )


def song_txt(music: Music):
    return Message([
        {
            "type": "text",
            "data": {
                "text": f"{music.id}. {music.title}\n"
            }
        },
        {
            "type": "image",
            "data": {
                "file": f"https://www.diving-fish.com/covers/{music.id}.jpg"
            }
        },
        {
            "type": "text",
            "data": {
                "text": f"\n{'/'.join(music.level)}"
            }
        }
    ])


def inner_level_q(ds1, ds2=None):
    result_set = []
    diff_label = ['Bas', 'Adv', 'Exp', 'Mst', 'ReM']
    if ds2 is not None:
        music_data = total_list.filter(ds=(ds1, ds2))
    else:
        music_data = total_list.filter(ds=ds1)
    for music in music_data:
        for i in music.diff:
            result_set.append((music['id'], music['title'], music['ds'][i], diff_label[i], music['level'][i]))
    return result_set


inner_level = on_command('inner_level ', aliases={'base '})


@inner_level.handle()
async def _(bot: Bot, event: Event, state: T_State):
    argv = str(event.get_message()).strip().split(" ")
    if len(argv) > 2 or len(argv) == 0:
        await inner_level.finish("命令格式为\nbase <定数>\nbase <定数下限> <定数上限>")
        return
    if len(argv) == 1:
        result_set = inner_level_q(float(argv[0]))
    else:
        result_set = inner_level_q(float(argv[0]), float(argv[1]))
    if len(result_set) > 50:
        await inner_level.finish("数据超出 50 条，请尝试缩小查询范围")
        return
    s = ""
    for elem in result_set:
        s += f"{elem[0]}. {elem[1]} {elem[3]} {elem[4]}({elem[2]})\n"
    await inner_level.finish(s.strip())


spec_rand = on_regex(r"^随个(?:dx|sd|标准)?[绿黄红紫白]?[0-9]+\+?", priority=0)


@spec_rand.handle()
async def _(bot: Bot, event: Event, state: T_State):
    level_labels = ['绿', '黄', '红', '紫', '白']
    regex = "随个((?:dx|sd|标准))?([绿黄红紫白]?)([0-9]+\+?)"
    res = re.match(regex, str(event.get_message()).lower())
    try:
        if res.groups()[0] == "dx":
            tp = ["DX"]
        elif res.groups()[0] == "sd" or res.groups()[0] == "标准":
            tp = ["SD"]
        else:
            tp = ["SD", "DX"]
        level = res.groups()[2]
        if res.groups()[1] == "":
            music_data = total_list.filter(level=level, type=tp)
        else:
            music_data = total_list.filter(level=level, diff=['绿黄红紫白'.index(res.groups()[1])], type=tp)
        await spec_rand.send(song_txt(music_data.random()))
    except Exception as e:
        print(e)
        await spec_rand.finish("随机命令错误，请检查语法")


mr = on_regex(r".*maimai.*什么")


@mr.handle()
async def _(bot: Bot, event: Event, state: T_State):
    await mr.finish(song_txt(total_list.random()))


search_music = on_regex(r"^search.+")


@search_music.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = "search(.+)"
    name = re.match(regex, str(event.get_message())).groups()[0].strip()
    if name == "":
        return
    res = total_list.filter(title_search=name)
    await search_music.finish(Message([
        {"type": "text",
         "data": {
             "text": f"{music['id']}. {music['title']}\n"
         }} for music in res]))


query_chart = on_regex(r"^([绿黄红紫白]?)id ([0-9]+)")


@query_chart.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = "([绿黄红紫白]?)id ([0-9]+)"
    groups = re.match(regex, str(event.get_message())).groups()
    level_labels = ['绿', '黄', '红', '紫', '白']
    if groups[0] != "":
        try:
            level_index = level_labels.index(groups[0])
            level_name = ['Basic', 'Advanced', 'Expert', 'Master', 'Re: MASTER']
            name = groups[1]
            music = total_list.by_id(name)
            chart = music['charts'][level_index]
            ds = music['ds'][level_index]
            level = music['level'][level_index]
            file = f"https://www.diving-fish.com/covers/{music['id']}.jpg"
            if len(chart['notes']) == 4:
                msg = f'''{level_name[level_index]} {level}({ds})
TAP: {chart['notes'][0]}
HOLD: {chart['notes'][1]}
SLIDE: {chart['notes'][2]}
BREAK: {chart['notes'][3]}
谱师: {chart['charter']}
'''
            else:
                msg = f'''{level_name[level_index]} {level}({ds})
TAP: {chart['notes'][0]}
HOLD: {chart['notes'][1]}
SLIDE: {chart['notes'][2]}
TOUCH: {chart['notes'][3]}
BREAK: {chart['notes'][4]}
谱师: {chart['charter']}
'''
            await query_chart.send(Message([
                {
                    "type": "text",
                    "data": {
                        "text": f"{music['id']}. {music['title']}\n"
                    }
                },
                {
                    "type": "image",
                    "data": {
                        "file": f"{file}"
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": msg
                    }
                }
            ]))
        except Exception:
            await query_chart.send("未找到该谱面")
    else:
        name = groups[1]
        music = total_list.by_id(name)
        try:
            file = f"https://www.diving-fish.com/covers/{music['id']}.jpg"
            await query_chart.send(Message([
                {
                    "type": "text",
                    "data": {
                        "text": f"{music['id']}. {music['title']}\n"
                    }
                },
                {
                    "type": "image",
                    "data": {
                        "file": f"{file}"
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": f"艺术家: {music['basic_info']['artist']}\n分类: {music['basic_info']['genre']}\nBPM: {music['basic_info']['bpm']}\n版本: {music['basic_info']['from']}\n难度: {'/'.join(music['level'])}"
                    }
                }
            ]))
        except Exception:
            await query_chart.send("未找到该乐曲")


wm_list = ['拼机', '推分', '越级', '下埋', '夜勤', '练底力', '练手法', '打旧框', '干饭', '抓绝赞', '收歌']

jrwm = on_command('今日运势', aliases={'今日运势'})


@jrwm.handle()
async def _(bot: Bot, event: Event, state: T_State):
    qq = int(event.get_user_id())
    h2 = hash(qq)
    h = h2
    rp = h % 100
    wm_value = []
    for i in range(11):
        wm_value.append(h & 3)
        h >>= 2
    s = f"今日人品值：{rp}\n"
    for i in range(11):
        if wm_value[i] == 3:
            s += f'宜 {wm_list[i]}\n'
        elif wm_value[i] == 0:
            s += f'忌 {wm_list[i]}\n'
    s += "tpz妹妹提醒您："  # 打机时不要大力拍打或滑动哦
    music = total_list[h2 % len(total_list)]
    await jrwm.finish(Message([
                                  {"type": "text", "data": {"text": s}},
                                  {"type": "image", "data": {
                                      "file": "file:///" + os.path.abspath("src/static/mai/pic/meimeinotice.jpg")}},
                                  {"type": "text", "data": {"text": "\n今日推荐歌曲："}}
                              ] + song_txt(music)))


music_aliases = defaultdict(list)
f = open('src/static/aliases.csv', 'r', encoding='utf-8')
tmp = f.readlines()
f.close()
for t in tmp:
    arr = t.strip().split('\t')
    for i in range(len(arr)):
        if arr[i] != "":
            music_aliases[arr[i].lower()].append(arr[0])

find_song = on_regex(r".+是啥歌")


@find_song.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = "(.+)是啥歌"
    name = re.match(regex, str(event.get_message())).groups()[0].strip().lower()
    if name not in music_aliases:
        await find_song.finish("未找到此歌曲\n舞萌 DX 歌曲别名收集计划：https://docs.qq.com/sheet/DRmFTeFl5d1BRa213")
        return
    result_set = music_aliases[name]
    if len(result_set) == 1:
        music = total_list.by_title(result_set[0])
        await find_song.finish(Message([{"type": "text", "data": {"text": "您要找的是不是"}}] + song_txt(music)))
    else:
        s = '\n'.join(result_set)
        await find_song.finish(f"您要找的可能是以下歌曲中的其中一首：\n{s}")


query_score = on_command('line')
query_score_text = '''此功能为查找某首歌分数线设计。
命令格式：line <难度+歌曲id> <分数线>
例如：line 白337 100
命令将返回分数线允许的 TAP GREAT 容错以及 BREAK 50落等价的 TAP GREAT 数。
以下为 TAP GREAT 的对应表：
GREAT/GOOD/MISS
TAP    1/2.5/5
HOLD   2/5/10
SLIDE  3/7.5/15
TOUCH  1/2.5/5
BREAK  5/12.5/25(外加200落)'''
query_score_mes = Message([{
    "type": "image",
    "data": {
        "file": f"base64://{str(image_to_base64(text_to_image(query_score_text)), encoding='utf-8')}"
    }
}])


@query_score.handle()
async def _(bot: Bot, event: Event, state: T_State):
    r = "([绿黄红紫白])(?:id)?([0-9]+)"
    argv = str(event.get_message()).strip().split(" ")
    if len(argv) == 1 and argv[0] == '帮助':
        await query_score.send(query_score_mes)
    elif len(argv) == 2:
        try:
            grp = re.match(r, argv[0]).groups()
            level_labels = ['绿', '黄', '红', '紫', '白']
            level_labels2 = ['Basic', 'Advanced', 'Expert', 'Master', 'Re:MASTER']
            level_index = level_labels.index(grp[0])
            chart_id = grp[1]
            line = float(argv[1])
            music = total_list.by_id(chart_id)
            chart: Dict[Any] = music['charts'][level_index]
            tap = int(chart['notes'][0])
            slide = int(chart['notes'][2])
            hold = int(chart['notes'][1])
            touch = int(chart['notes'][3]) if len(chart['notes']) == 5 else 0
            brk = int(chart['notes'][-1])
            total_score = 500 * tap + slide * 1500 + hold * 1000 + touch * 500 + brk * 2500
            break_bonus = 0.01 / brk
            break_50_reduce = total_score * break_bonus / 4
            reduce = 101 - line
            if reduce <= 0 or reduce >= 101:
                raise ValueError
            await query_chart.send(f'''{music['title']} {level_labels2[level_index]}
    分数线 {line}% 允许的最多 TAP GREAT 数量为 {(total_score * reduce / 10000):.2f}(每个-{10000 / total_score:.4f}%),
    BREAK 50落(一共{brk}个)等价于 {(break_50_reduce / 100):.3f} 个 TAP GREAT(-{break_50_reduce / total_score * 100:.4f}%)''')
            if random.random() < 0.3:
                await query_chart.send(Message([{"type": "image", "data": {
                    "file": "file:///" + os.path.abspath("src/static/mai/pic/meimeiyiban.jpg")}}]))
        except Exception as e:
            print(e)
            await query_chart.send("格式错误或未找到乐曲，输入“line 帮助”以查看帮助信息")


best_40_pic_old = on_command('b40')


@best_40_pic_old.handle()
async def _(bot: Bot, event: Event, state: T_State):
    await best_40_pic_old.send(Message([
        {
            "type": "text",
            "data": {
                "text": f"是\"妹妹b40\"谢谢"
            }
        },
        {
            "type": "image",
            "data": {
                "file": "file:///" + os.path.abspath("src/static/mai/pic/meimeib40.jpg")
            }
        }
    ]))


best_40_pic = on_command('妹妹b40')


@best_40_pic.handle()
async def _(bot: Bot, event: Event, state: T_State):
    username = str(event.get_message()).strip()
    # print(event.message_id)
    if username == "":
        payload = {'qq': str(event.get_user_id())}
    else:
        payload = {'username': username}
    img, success = await generate(payload)
    if success == 400:
        await best_40_pic.send(
            "未找到此玩家，请确保此玩家的用户名和查分器中的用户名相同。\n查分器绑定教程：https://www.diving-fish.com/maimaidx/prober_guide")
    elif success == 403:
        await best_40_pic.send("该用户禁止了其他人获取数据。")
    else:
        await best_40_pic.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.image(f"base64://{str(image_to_base64(img), encoding='utf-8')}")
        ]))


ra_analysis = on_regex(r"^([0-9]*)底分分析(.*)$")


@ra_analysis.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = r"^([0-9]*)底分分析(.*)$"
    res = re.match(regex, str(event.get_message()))
    num = 3
    username = ""
    try:
        if res.group(1) != "":
            num = int(res.group(1))
        if res.group(2) != "":
            username = str(res.group(2)).strip()
    except Exception as e:
        print("Exception: " + e)
        await ra_analysis.finish("命令错误，请检查语法")
        return

    if num > 100:
        await ra_analysis.finish("数据量超出上限，请缩小随机数量")
        return

    # print(event.message_id)
    if username == "":
        payload = {'qq': str(event.get_user_id())}
    else:
        payload = {'username': username}
    img, success = await analyze(payload, num)
    if success == 400:
        await ra_analysis.send(
            "未找到此玩家，请确保此玩家的用户名和查分器中的用户名相同。\n查分器绑定教程：https://www.diving-fish.com/maimaidx/prober_guide")
    elif success == 403:
        await ra_analysis.send("该用户禁止了其他人获取数据。")
    elif success == -1:
        await ra_analysis.send("请先游玩游戏")
    else:
        await ra_analysis.send(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.image(f"base64://{str(image_to_base64(img), encoding='utf-8')}")
        ]))


disable_guess_music = on_command('猜歌设置', priority=0)


@disable_guess_music.handle()
async def _(bot: Bot, event: Event):
    if event.message_type != "group":
        return
    arg = str(event.get_message())
    group_members = await bot.get_group_member_list(group_id=event.group_id)
    for m in group_members:
        if m['user_id'] == event.user_id:
            break
    su = get_driver().config.superusers
    if m['role'] != 'owner' and m['role'] != 'admin' and str(m['user_id']) not in su:
        await disable_guess_music.finish("只有管理员可以设置猜歌")
        return
    db = get_driver().config.db
    c = await db.cursor()
    # await c.execute(f'create table guess_table (group_id bigint, enabled bit);')
    if arg == '启用':
        await c.execute(f'update guess_table set enabled=1 where group_id={event.group_id}')
    elif arg == '禁用':
        await c.execute(f'update guess_table set enabled=0 where group_id={event.group_id}')
    else:
        await disable_guess_music.finish("请输入 猜歌设置 启用/禁用")
    await db.commit()
    await disable_guess_music.finish("设置成功")


guess_dict: Dict[Tuple[str, str], GuessObject] = {}
guess_cd_dict: Dict[Tuple[str, str], float] = {}
guess_music = on_command('妹妹猜歌', priority=0)


async def guess_music_loop(bot: Bot, event: Event, state: T_State):
    await asyncio.sleep(10)
    guess: GuessObject = state["guess_object"]
    if guess.is_end:
        return
    cycle = state["cycle"]
    if cycle == 0:
        if random.random() < 0.3:
            asyncio.create_task(bot.send(event, f"{cycle}/7 这歌真不难"))
        else:
            state["cycle"] += 1
            asyncio.create_task(bot.send(event, f"{cycle + 1}/7 这首歌" + guess.guess_options[cycle]))
    elif cycle < 7:
        asyncio.create_task(bot.send(event, f"{cycle}/7 这首歌" + guess.guess_options[cycle - 1]))
    else:
        asyncio.create_task(bot.send(event, Message([
            MessageSegment.text("7/7 这首歌封面的一部分是："),
            MessageSegment.image("base64://" + str(guess.b64image, encoding="utf-8")),
            MessageSegment.text("答案将在 30 秒后揭晓")
        ])))
        asyncio.create_task(give_answer(bot, event, state))
        return
    state["cycle"] += 1
    asyncio.create_task(guess_music_loop(bot, event, state))


async def give_answer(bot: Bot, event: Event, state: T_State):
    await asyncio.sleep(30)
    guess: GuessObject = state["guess_object"]
    if guess.is_end:
        return
    asyncio.create_task(bot.send(event, Message(
        [MessageSegment.text("答案是：" + f"{guess.music['id']}. {guess.music['title']}\n"),
         MessageSegment.image(f"https://www.diving-fish.com/covers/{guess.music['id']}.jpg")])))
    del guess_dict[state["k"]]


@guess_music.handle()
async def _(bot: Bot, event: Event, state: T_State):
    mt = event.message_type
    k = (mt, event.user_id if mt == "private" else event.group_id)
    if mt == "group":
        gid = event.group_id
        db = get_driver().config.db
        c = await db.cursor()
        await c.execute(f"select * from guess_table where group_id={gid}")
        data = await c.fetchone()
        if data is None:
            await c.execute(f'insert into guess_table values ({gid}, 1)')
        elif data[1] == 0:
            await guess_music.send("本群已禁用猜歌")
            return
        if k in guess_dict:
            if k in guess_cd_dict and time.time() > guess_cd_dict[k] - 400:
                # 如果已经过了 200 秒则自动结束上一次
                del guess_dict[k]
            else:
                await guess_music.send("当前已有正在进行的猜歌")
                return
    # whitelists = get_driver().config.whitelists
    # if not (mt == "group" and gid in whitelists):
    #     if len(guess_dict) >= 5:
    #         await guess_music.finish("千雪有点忙不过来了。现在正在猜的群有点多，晚点再试试如何？")
    #         return
    #     if k in guess_cd_dict and time.time() < guess_cd_dict[k]:
    #         await guess_music.finish(f"已经猜过啦，下次猜歌会在 {time.strftime('%H:%M', time.localtime(guess_cd_dict[k]))} 可用噢")
    #         return
    guess = GuessObject()
    guess_dict[k] = guess
    state["k"] = k
    state["guess_object"] = guess
    state["cycle"] = 0
    guess_cd_dict[k] = time.time() + 600
    await guess_music.send(
        "我将从热门乐曲中选择一首歌，并描述它的一些特征，请输入歌曲的【id】、【歌曲标题】或【歌曲标题中 5 个以上连续的字符】进行猜歌（DX乐谱和标准乐谱视为两首歌）。猜歌时查歌等其他命令依然可用。\n警告：这个命令可能会很刷屏，管理员可以使用【猜歌设置】指令进行设置。")
    asyncio.create_task(guess_music_loop(bot, event, state))


guess_music_solve = on_message(priority=20)


@guess_music_solve.handle()
async def _(bot: Bot, event: Event, state: T_State):
    mt = event.message_type
    k = (mt, event.user_id if mt == "private" else event.group_id)
    if k not in guess_dict:
        return
    ans = str(event.get_message())
    guess = guess_dict[k]
    # await guess_music_solve.send(ans + "|" + guess.music['id'])
    if ans == guess.music['id'] or (ans.lower() == guess.music['title'].lower()) or (
            len(ans) >= 5 and ans.lower() in guess.music['title'].lower()):
        guess.is_end = True
        del guess_dict[k]
        group_id = event.__getattribute__('group_id')
        sender_id = event.get_user_id()
        if group_id is None:
            event.__delattr__('group_id')
        else:
            guess_count_dict = shelve.open('src/static/guess.db', writeback=True)
            if str(group_id) not in guess_count_dict:
                guess_count_dict[str(group_id)] = {}
            if str(sender_id) not in guess_count_dict[str(group_id)]:
                guess_count_dict[str(group_id)][str(sender_id)] = 0
            guess_count_dict[str(group_id)][str(sender_id)] += 1
            guess_count_dict.close()
        await guess_music_solve.finish(Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("猜对了，答案是：" + f"{guess.music['id']}. {guess.music['title']}\n"),
            MessageSegment.image(f"https://www.diving-fish.com/covers/{guess.music['id']}.jpg")
        ]))


async def send_guess_stat(group_id: int, bot: Bot):
    guess_count_dict = shelve.open('src/static/guess.db')
    if str(group_id) not in guess_count_dict:
        guess_count_dict.close()
        return
    else:
        group_stat = guess_count_dict[str(group_id)]
        guess_count_dict.close()
        sorted_dict = {k: v for k, v in sorted(group_stat.items(), key=lambda item: item[1], reverse=True)}
        index = 0
        data = []
        for k in sorted_dict:
            data.append((k, sorted_dict[k]))
            index += 1
            if index == 3:
                break
        await bot.send_msg(group_id=group_id, message="接下来公布一下我上次失忆以来，本群最闲着没事干玩猜歌的人")
        await asyncio.sleep(1)
        if len(data) == 3:
            await bot.send_msg(group_id=group_id, message=Message([
                {"type": "text", "data": {"text": "第三名，"}},
                {"type": "at", "data": {"qq": f"{data[2][0]}"}},
                {"type": "text", "data": {"text": f"，一共猜对了{data[2][1]}次，只能说一般"}},
            ]))
            await asyncio.sleep(1)
        if len(data) >= 2:
            await bot.send_msg(group_id=group_id, message=Message([
                {"type": "text", "data": {"text": "第二名，"}},
                {"type": "at", "data": {"qq": f"{data[1][0]}"}},
                {"type": "text", "data": {"text": f"，一共猜对了{data[1][1]}次，猜对这么多日文歌，你是不是日本人"}},
            ]))
            await asyncio.sleep(1)
        await bot.send_msg(group_id=group_id, message=Message([
            {"type": "text", "data": {"text": "第一名，"}},
            {"type": "at", "data": {"qq": f"{data[0][0]}"}},
            {"type": "text", "data": {"text": f"，一共猜对了{data[0][1]}次，基本上全靠别人查出来抢答，有这手速怎么不AP白潘"}},
        ]))


guess_stat = on_command("本群猜歌情况")


@guess_stat.handle()
async def _(bot: Bot, event: Event, state: T_State):
    group_id = event.group_id
    await send_guess_stat(group_id, bot)


sing = on_regex(r"^(妹妹唱歌)( )?(id)?( )?([0-9]{1,5})?$", block=True)


@sing.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    regex = r"^(妹妹唱歌)( )?(id)?( )?([0-9]{1,5})?$"
    res = re.match(regex, str(event.get_message()))
    try:
        if res.group(5) is not None:
            music = total_list.by_id(res.group(5))
            if music is None:
                music = {'id': res.group(5), 'title': '', 'basic_info': {'artist': ''}}
        else:
            music = total_list.random()
    except Exception as e:
        print("Exception: " + e)
        await sing.finish("命令错误，请检查语法")
        return
    response = await search_audio(music)
    await sing.finish(response)


sing_aliases = on_regex(r"^妹妹唱(.+)$", priority=2, block=True)


@sing_aliases.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    regex = "妹妹唱(.+)"
    name = re.match(regex, str(event.get_message())).groups()[0].strip().lower()
    music = total_list.by_title(name)
    if music is None:
        if name not in music_aliases:
            await sing_aliases.finish("未找到此歌曲\n舞萌 DX 歌曲别名收集计划：https://docs.qq.com/sheet/DRmFTeFl5d1BRa213")
            return
        result_set = music_aliases[name]
        music = total_list.by_title(random.choice(result_set))
        response = await search_audio(music)
        await sing_aliases.finish(response)
    else:
        response = await search_audio(music)
        await sing_aliases.finish(response)


async def search_audio(music: Music):
    music_id = music['id']
    sound_id = music_id[1:5].lstrip("0") if len(music_id) == 5 else music_id
    print(sound_id)
    tmp_secret_id, tmp_secret_key, temp_token = await create_temp_token(sound_id)
    key = f"sound/{sound_id}.mp3"
    tmp_config = CosConfig(Region=region, SecretId=tmp_secret_id, SecretKey=tmp_secret_key)
    tmp_client = CosS3Client(tmp_config)
    if not client.object_exists(Bucket=bucket_name, Key=key):
        return "未找到该歌曲"
    response = parse.unquote(
        tmp_client.get_presigned_url(Bucket=bucket_name, Key=key, Params={"x-cos-security-token": temp_token},
                                     Method='GET', Expired=600))
    print(response)
    return MessageSegment.music_custom("",
                                       response,
                                       f"{music_id}. {music['title']}",
                                       music['basic_info']['artist'],
                                       f"https://www.diving-fish.com/covers/{music_id}.jpg")


async def create_temp_token(sound_id: str):
    req_config = {
        'url': 'https://sts.tencentcloudapi.com/',
        # 域名，非必须，默认为 sts.tencentcloudapi.com
        'domain': 'sts.tencentcloudapi.com',
        # 临时密钥有效时长，单位是秒
        'duration_seconds': 600,
        'secret_id': secret_id,
        # 固定密钥
        'secret_key': secret_key,
        # 换成你的 bucket
        'bucket': bucket_name,
        # 换成 bucket 所在地区
        'region': region,
        # 这里改成允许的路径前缀，可以根据自己网站的用户登录态判断允许上传的具体路径
        # 例子： a.jpg 或者 a/* 或者 * (使用通配符*存在重大安全风险, 请谨慎评估使用)
        'allow_prefix': f'sound/{sound_id}.mp3',
        # 密钥的权限列表。简单上传和分片需要以下的权限，其他权限列表请看 https://cloud.tencent.com/document/product/436/31923
        'allow_actions': [
            # 下载操作
            "name/cos:GetObject"
        ],

    }

    try:
        sts = Sts(req_config)
        response = sts.get_credential()
        return response["credentials"]["tmpSecretId"], \
               response["credentials"]["tmpSecretKey"], \
               response["credentials"]["sessionToken"]
    except Exception as e:
        print(e)


records_by_level = on_regex(r"^([0-9]+)(\+)?(分数列表)([0-9]+)?$", block=True)


@records_by_level.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = r"([0-9]+)(\+)?(分数列表)([0-9]*)?"
    res = re.match(regex, str(event.get_message()))
    try:
        if 1 <= int(res.group(1)) <= 15:
            level = res.group(1)
            if res.group(2):
                level += res.group(2)
        else:
            await records_by_level.send(
                MessageSegment.image("file:///" + os.path.abspath("src/static/mai/pic/meimeib40.jpg")))
            return
        if res.group(4):
            page = int(res.group(4))
        else:
            page = 1
    except Exception as e:
        print("Exception: " + e)
        await sing.finish("命令错误，请检查语法")
        return

    res, status = await get_records_by_level(level, page, str(event.get_user_id()))

    if status == 400:
        await records_by_level.send(
            "未找到此玩家，请确保此玩家的用户名和查分器中的用户名相同。\n查分器绑定教程：https://www.diving-fish.com/maimaidx/prober_guide")
    elif status == 403:
        await records_by_level.send("该用户禁止了其他人获取数据。")
    elif status == -1:
        return
    else:
        await records_by_level.finish(MessageSegment.image(f"base64://{str(image_to_base64(res), encoding='utf-8')}"))
