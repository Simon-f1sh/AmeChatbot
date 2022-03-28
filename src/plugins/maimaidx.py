import shutil
from collections import defaultdict
from typing import List, Dict, Any, Tuple

from nonebot import on_command, on_message, on_notice, on_regex, get_driver, require, get_bots
from nonebot.log import logger
from nonebot.permission import Permission
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters import Event, Bot
from nonebot.adapters.cqhttp import Message, MessageSegment, GroupMessageEvent, PrivateMessageEvent, ActionFailed
from nonebot.permission import SUPERUSER
from nonebot.adapters.cqhttp.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor

from src.libraries.maimaidx_guess import GuessObject
from src.libraries.image import image_to_base64, text_to_image
from src.libraries.tool import hash
from src.libraries.maimaidx_music import total_list, search_length, search_bpm, search_charter, search_artist, search_diff, search_pop_rank, Music, update_chart_stats_and_count_list
from src.libraries.image import *
from src.libraries.maimai_best_40 import generate, analyze
from src.libraries.maimai_best_50 import generate50
from src.libraries.maimai_records import get_records_by_level_or_ds
from src.libraries.CONST import record_folder, poke_img_folder, audio_folder, food_folder, mai_tmp_folder
from src.libraries.qcloud import search_audio, download_music_and_to_clip

import random
import time
import re
import os
import shelve
import asyncio

driver = get_driver()

scheduler = require("nonebot_plugin_apscheduler").scheduler


if os.path.exists(mai_tmp_folder):
    # Clean the temp files and recreate the folder
    shutil.rmtree(mai_tmp_folder)
os.makedirs(mai_tmp_folder)
print("The mai temp folder is created!")


@event_preprocessor
async def preprocessor(bot, event, state):
    if hasattr(event, 'message_type') and event.message_type == "private" and event.sub_type != "friend":
        raise IgnoredException("not reply group temp message")


async def sandian():
    (bot,) = get_bots().values()
    await bot.send_group_msg(group_id=879106299, message=MessageSegment.image(
        "file:///" + os.path.abspath("src/static/mai/pic/sandian.jpg")))


@driver.on_startup
def _():
    logger.info("Load help text successfully")
    help_text: dict = get_driver().config.help_text
    help_text['mai'] = ('查看舞萌相关功能', "help_mai.txt")
    scheduler.add_job(
        sandian,
        trigger='cron',
        hour=15,
        minute=0
    )
    scheduler.add_job(
        update_chart_stats_and_count_list,
        trigger='cron',
        hour=0,
        minute=0
    )


@driver.on_bot_connect
async def _(bot: Bot):
    groups = await bot.get_group_list()
    for group in groups:
        await preload_audio_guess(group['group_id'])


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
    if len(argv) > 2 or (len(argv) == 1 and len(argv[0]) == 0):
        await inner_level.finish("命令格式为\nbase <定数>\nbase <定数下限> <定数上限>")
        return
    if len(argv) == 1:
        result_set = inner_level_q(float(argv[0]))
    else:
        result_set = inner_level_q(float(argv[0]), float(argv[1]))

    if len(result_set) == 0:
        await inner_level.finish("无查询结果")
        return

    if len(result_set) > 200:
        await inner_level.finish("数据超出 200 条，请尝试缩小查询范围")
        return
    s = ""
    result_set = sorted(result_set, key=lambda k: (k[2], int(k[0]))) # k[2]为定数 k[0]为id
    for elem in result_set:
        s += f"{elem[0]}. {elem[1]} {elem[3]} {elem[4]}({elem[2]})\n"

    img = text_to_image(s.strip())
    await inner_level.finish(MessageSegment.image(f"base64://{str(image_to_base64(img), encoding='utf-8')}"))


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
        except ActionFailed:
            await query_chart.send("风控捏")
            print(f"风控信息: {music}")
        except Exception as e:
            print(e)
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
                        "text": f"艺术家: {music['basic_info']['artist']}\n分类: {music['basic_info']['genre']}\nBPM: {music['basic_info']['bpm']}\n版本: {music['basic_info']['from']}\n难度: {'/'.join(music['level'])}\n定数: {'/'.join(map(str, music['ds']))}"
                    }
                }
            ]))
        except ActionFailed:
            await query_chart.send("风控捏")
            print(f"风控信息: {music}")
        except Exception as e:
            print(e)
            await query_chart.send("未找到该乐曲")


bpm_search = on_command("bpm", aliases={"BPM", "查bpm", "查BPM"}, rule=to_me())


@bpm_search.handle()
async def _(bot: Bot, event: Event, state: T_State):
    bpm = str(event.get_message()).strip().split(" ")[0]
    result = await search_bpm(bpm)
    if result[0]:
        await bpm_search.finish(
            MessageSegment.image(f"base64://{str(image_to_base64(text_to_image(result[0])), encoding='utf-8')}"))
    else:
        await bpm_search.finish(result[1])


artist_search = on_command('artist', aliases={"查曲师", "查艺术家", "查作者"}, rule=to_me())


@artist_search.handle()
async def _(bot: Bot, event: Event, state: T_State):
    artist = str(event.get_message()).strip()
    result = await search_artist(artist.lower())
    if result[0]:
        await artist_search.finish(
            MessageSegment.image(f"base64://{str(image_to_base64(text_to_image(result[0])), encoding='utf-8')}"))
    else:
        await artist_search.finish(result[1])


charter_search = on_command('charter', aliases={'查谱师', '查谱作者'}, rule=to_me())


@charter_search.handle()
async def _(bot: Bot, event: Event, state: T_State):
    charter = str(event.get_message()).strip()
    result = await search_charter(charter.lower())
    if result[0]:
        await charter_search.finish(
            MessageSegment.image(f"base64://{str(image_to_base64(text_to_image(result[0])), encoding='utf-8')}"))
    else:
        await charter_search.finish(result[1])


song_len = on_command('查长度', aliases={'歌曲长度'}, rule=to_me())


@song_len.handle()
async def _(bot: Bot, event: Event, state: T_State):
    music_id = str(event.get_message()).strip().split(" ")[0]
    state["music_id"] = music_id
    asyncio.create_task(get_music_length(bot, event, state))


async def get_music_length(bot, event: Event, state: T_State):
    result = await search_length(state["music_id"])
    await bot.send(event, result)


diff_search = on_command("查难度", rule=to_me())


@diff_search.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = "([绿黄红紫白])(id)?( )*([0-9]+)"
    res = re.match(regex, str(event.get_message()).strip())
    if not res:
        await diff_search.finish("输入有误，请检查语法")
        return
    diff_labels = ['绿', '黄', '红', '紫', '白']
    diff_index = diff_labels.index(res.group(1))
    result = await search_diff(diff_index, diff_labels, res.group(4))
    await diff_search.send(result[0] if result[0] else result[1])


pop_rank = on_regex(r"^(查热度)( )*([绿黄红紫白]?)(id)?( )*([0-9]+)$", rule=to_me())


@pop_rank.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = "(查热度)( )*([绿黄红紫白]?)(id)?( )*([0-9]+)"
    diff_labels = ['绿', '黄', '红', '紫', '白']
    diff_index = None
    res = re.match(regex, str(event.get_message()))
    try:
        if res.group(3):
            diff_index = diff_labels.index(res.group(3))
        if res.group(4):
            is_id = True
            music_id_or_rank = res.group(6)
        else:
            is_id = False
            music_id_or_rank = int(res.group(6))
    except Exception as e:
        print(e)
        await pop_rank.finish("命令错误，请检查语法")
        return

    result = await search_pop_rank(diff_labels, diff_index, is_id, music_id_or_rank)

    if result[0]:
        await pop_rank.finish(result[0])
    else:
        await pop_rank.finish(result[1])


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
    s += "今天建议吃："  # 打机时不要大力拍打或滑动哦
    music = total_list[h2 % len(total_list)]
    random.seed(h2)
    food_file = random.choice(os.listdir(food_folder))
    try:
        await jrwm.finish(Message([
                                      {"type": "text", "data": {"text": s}},
                                      {"type": "image", "data": {
                                          "file": "file:///" + os.path.abspath(f"{food_folder}{food_file}")}},
                                      {"type": "text", "data": {"text": "\n今日推荐歌曲："}}
                                  ] + song_txt(music)))
    except ActionFailed:
        await jrwm.send("风控捏")
        print(f"风控信息: {s}\n{food_folder}{food_file}\n{music}")


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
        response = "您要找的可能是以下歌曲中的其中一首："
        for result in result_set:
            music = total_list.by_title(result)
            response += f"\n{music.id}. {music.title}"
        await find_song.finish(response)


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
            await query_score.send(f'''{music['title']} {level_labels2[level_index]}
    分数线 {line}% 允许的最多 TAP GREAT 数量为 {(total_score * reduce / 10000):.2f}(每个-{10000 / total_score:.4f}%),
    BREAK 50落(一共{brk}个)等价于 {(break_50_reduce / 100):.3f} 个 TAP GREAT(-{break_50_reduce / total_score * 100:.4f}%)''')
            if random.random() < 0.3:
                await query_score.send(Message([{"type": "image", "data": {
                    "file": "file:///" + os.path.abspath(f"{poke_img_folder}saikouka.jpg")}}]))
        except ActionFailed:
            await query_score.send("风控捏")
            print(f'''风控信息: {music['title']} {level_labels2[level_index]}
    分数线 {line}% 允许的最多 TAP GREAT 数量为 {(total_score * reduce / 10000):.2f}(每个-{10000 / total_score:.4f}%),
    BREAK 50落(一共{brk}个)等价于 {(break_50_reduce / 100):.3f} 个 TAP GREAT(-{break_50_reduce / total_score * 100:.4f}%)''')
        except Exception as e:
            print(e)
            await query_score.send("格式错误或未找到乐曲，输入“line 帮助”以查看帮助信息")


best_40_pic = on_command('b40')


@best_40_pic.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if event.is_tome():
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
    else:
        await best_40_pic.send(Message([
            {
                "type": "text",
                "data": {
                    "text": f"是\"糖糖b40\"谢谢"
                }
            },
            {
                "type": "image",
                "data": {
                    "file": "file:///" + os.path.abspath("src/static/mai/pic/yyln.jpg")
                }
            }
        ]))


best_50_pic = on_command('b50')


@best_50_pic.handle()
async def _(bot: Bot, event: Event, state: T_State):
    if event.is_tome():
        username = str(event.get_message()).strip()
        if username == "":
            payload = {'qq': str(event.get_user_id()),'b50':True}
        else:
            payload = {'username': username,'b50':  True}
        img, success = await generate50(payload)
        if success == 400:
            await best_50_pic.send("未找到此玩家，请确保此玩家的用户名和查分器中的用户名相同。")
        elif success == 403:
            await best_50_pic.send("该用户禁止了其他人获取数据。")
        else:
            await best_50_pic.send(Message([
                {
                    "type": "image",
                    "data": {
                        "file": f"base64://{str(image_to_base64(img), encoding='utf-8')}"
                    }
                }
            ]))
    else:
        await best_40_pic.send(Message([
            {
                "type": "text",
                "data": {
                    "text": f"是\"糖糖b50\"谢谢"
                }
            },
            {
                "type": "image",
                "data": {
                    "file": "file:///" + os.path.abspath("src/static/mai/pic/yyln.jpg")
                }
            }
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
guess_music = on_regex(r"^(文字|语音)?(猜歌)$", priority=0)
preload_audio_guess_dict: Dict[str, GuessObject] = {}


async def preload_audio_guess(group_id: int):
    guess = GuessObject(False)
    preload_audio_guess_dict[str(group_id)] = guess
    guess.clip_url, guess.temp_path = await download_music_and_to_clip(guess.music['id'])


async def audio_guess_music_loop(bot, event: Event, state: T_State):
    guess: GuessObject = state["guess_object"]
    await bot.send(event, MessageSegment.record(guess.clip_url))
    await asyncio.sleep(30)
    if guess.is_end:
        return
    asyncio.create_task(bot.send(event, Message(
        [MessageSegment.text(f"没有人猜对捏。\n答案是：{guess.music['id']}. {guess.music['title']}\n"),
         MessageSegment.image(f"https://www.diving-fish.com/covers/{guess.music['id']}.jpg")])))
    if guess.temp_path:
        if os.path.exists(guess.temp_path):
            os.remove(guess.temp_path)
    del guess_dict[state["k"]]


async def text_guess_music_loop(bot: Bot, event: Event, state: T_State):
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
    asyncio.create_task(text_guess_music_loop(bot, event, state))


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
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    mt = str(event.message_type)
    k = (mt, str(event.user_id) if mt == "private" else str(event.group_id))
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
    regex = r"(文字|语音)?(猜歌)"
    res = re.match(regex, str(event.get_message()).lower())
    try:
        if res.group(1):
            if res.group(1) == "文字":
                is_text = True
            else:
                is_text = False
        else:
            is_text = random.choice([True, False])
    except Exception as e:
        print("Exception" + str(e))
        await guess_music.finish("命令错误，请检查语法")
        return

    if is_text:
        guess = GuessObject(is_text)
    else:
        guess = preload_audio_guess_dict.get(str(event.group_id))
        if not guess or not os.path.exists(guess.temp_path):
            guess = GuessObject(is_text)
            guess.clip_url, guess.temp_path = await download_music_and_to_clip(guess.music['id'])
    guess_dict[k] = guess
    state["k"] = k
    state["guess_object"] = guess
    guess_cd_dict[k] = time.time() + 600
    if is_text:
        state["cycle"] = 0
        await guess_music.send(
            "我将从乌蒙地插2021的全部歌曲中选择一首歌，并描述它的一些特征，"
            "请输入歌曲的【id】、【歌曲标题】或【歌曲标题中 5 个以上连续的字符】进行猜歌（DX乐谱和标准乐谱视为两首歌）。"
            "猜歌时查歌等其他命令依然可用。\n警告：这个命令可能会很刷屏，管理员可以使用【猜歌设置】指令进行设置。")
        asyncio.create_task(text_guess_music_loop(bot, event, state))
    else:
        await guess_music.send(
            "我将从乌蒙地插2021的全部歌曲中随机选择一首歌，从中截取5秒的音频。\n"
            "请输入歌曲的【id】、【歌曲标题】或【歌曲标题中 5 个以上连续的字符】进行猜歌。"
            "\n时间限制为30秒。猜歌时查歌等其他命令依然可用。\n警告：这个命令可能会很刷屏，管理员可以使用【猜歌设置】指令进行设置。")
        asyncio.create_task(audio_guess_music_loop(bot, event, state))
        asyncio.create_task(preload_audio_guess(event.group_id))


guess_music_solve = on_message(priority=20)


@guess_music_solve.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    mt = str(event.message_type)
    k = (mt, str(event.user_id) if mt == "private" else str(event.group_id))
    if k not in guess_dict:
        return
    ans = str(event.get_message())
    guess = guess_dict[k]
    # await guess_music_solve.send(ans + "|" + guess.music['id'])
    if ans == guess.music['id'] or (ans.lower() == guess.music['title'].lower()) or (
            len(ans) >= 5 and ans.lower() in guess.music['title'].lower()):
        guess.is_end = True
        if guess.temp_path:
            if os.path.exists(guess.temp_path):
                os.remove(guess.temp_path)
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


guess_music_cancel = on_regex(r"^(不猜了)$", permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER)


@guess_music_cancel.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    mt = str(event.message_type)
    k = (mt, str(event.user_id) if mt == "private" else str(event.group_id))
    if k not in guess_dict:
        return
    guess = guess_dict[k]
    guess.is_end = True
    if guess.temp_path:
        if os.path.exists(guess.temp_path):
            os.remove(guess.temp_path)
    del guess_dict[k]
    await guess_music_cancel.finish("这个阿P就是逊啦")


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


guess_stat = on_command("本群猜歌情况", rule=to_me())


@guess_stat.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    await send_guess_stat(group_id, bot)


sing = on_regex(r"^(唱歌)( )?(id)?( )?([0-9]{1,5})?$", rule=to_me(), block=True)


@sing.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    regex = r"^(唱歌)( )?(id)?( )?([0-9]{1,5})?$"
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


sing_aliases = on_regex(r"^唱(.+)$", rule=to_me(), priority=2, block=True)


@sing_aliases.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    regex = "唱(.+)"
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


records_by_level = on_regex(r"^(([0-9]+\+?)|([0-9]+\.[0-9]{1}))(分数列表)([0-9]+)?$", block=True)


@records_by_level.handle()
async def _(bot: Bot, event: Event, state: T_State):
    regex = r"(([0-9]+\+?)|([0-9]+\.[0-9]{1}))(分数列表)([0-9]+)?"
    res = re.match(regex, str(event.get_message()))
    level = None
    ds = None
    try:
        if res.group(2) and 1 <= int(res.group(2).replace("+", "")) <= 15:
            level = res.group(2)
        elif res.group(3) and 1.0 <= float(res.group(3)) <= 15.0:
            ds = res.group(3)
        else:
            await records_by_level.send(
                MessageSegment.image("file:///" + os.path.abspath("src/static/mai/pic/xiaoshi.jpg")))
            return
        if res.group(5):
            page = int(res.group(5))
        else:
            page = 1
    except Exception as e:
        print("Exception: " + e)
        await sing.finish("命令错误，请检查语法")
        return

    print(level)
    print(ds)
    res, status = await get_records_by_level_or_ds(page=page, qq=str(event.get_user_id()), level=level, ds=ds)

    if status == 400:
        await records_by_level.send(
            "未找到此玩家，请确保此玩家的用户名和查分器中的用户名相同。\n查分器绑定教程：https://www.diving-fish.com/maimaidx/prober_guide")
    elif status == 403:
        await records_by_level.send("该用户禁止了其他人获取数据。")
    elif status == -1:
        await records_by_level.finish(MessageSegment.image("file:///" + os.path.abspath("src/static/mai/pic/mfywakaranai.jpg")))
    else:
        await records_by_level.finish(MessageSegment.image(f"base64://{str(image_to_base64(res), encoding='utf-8')}"))
