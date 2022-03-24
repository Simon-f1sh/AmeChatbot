import random
import re
import os
import sys
import shelve

import nonebot
import psutil
import platform
import urllib.request
import requests
from random import randint
import asyncio

from nonebot import on_command, on_message, on_notice, require, get_driver, on_regex, get_bots, logger
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Message, Event, Bot, MessageEvent, GroupMessageEvent, MessageSegment
from nonebot.permission import SUPERUSER
from nonebot.adapters.cqhttp.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.exception import IgnoredException
from nonebot.message import event_preprocessor

from src.libraries.image import image_to_base64, path, draw_text, get_jlpx, text_to_image, wc_to_image, bytes_to_base64
from src.libraries.word_cloud import fetch_records, wordcloud_generate
from src.libraries.CONST import record_folder, poke_img_folder, audio_folder, general_sticker_folder, ongeki_sticker_folder, food_folder, help_folder
from src.libraries.tool import stat
from src.libraries.baidu_translate import translate_to_zh

import time
from datetime import datetime, timedelta
import pytz
from collections import defaultdict

driver = get_driver()

SH = pytz.timezone('Asia/Shanghai')
scheduler = require("nonebot_plugin_apscheduler").scheduler

if not os.path.exists(record_folder):
    # Create a new directory because it does not exist
    os.makedirs(record_folder)
    print("The record folder is created!")


@event_preprocessor
async def preprocessor(bot, event, state):
    if hasattr(event, 'message_type') and event.message_type == "private" and event.sub_type != "friend":
        raise IgnoredException("not reply group temp message")


async def weekly_wordcloud():
    (bot,) = get_bots().values()
    start_date = (datetime.now(SH) - timedelta(days=7)).strftime("%Y%m%d")
    end_date = (datetime.now(SH) - timedelta(days=1)).strftime("%Y%m%d")
    logger.info(f"WordCloud Start Date: {start_date}")
    logger.info(f"WordCloud End Date: {end_date}")
    await bot.send_group_msg(group_id=879106299, message="看看宅宅们上周说了什么...")
    result_wc = wordcloud_generate(fetch_records(record_folder, start_date, end_date))
    await bot.send_group_msg(group_id=879106299, message=MessageSegment.image(
        f"base64://{str(image_to_base64(wc_to_image(result_wc)), encoding='utf-8')}"))


@driver.on_startup
def _():
    help_text: dict = get_driver().config.help_text
    help_text['ame'] = ('花里胡哨功能', "help_ame.txt")
    scheduler.add_job(
        weekly_wordcloud,
        trigger='cron',
        day_of_week='mon',
        hour=0,
        minute=0,
    )


help = on_command('help')


@help.handle()
async def _(bot: Bot, event: Event, state: T_State):
    v = str(event.get_message()).strip()
    help_text: dict = get_driver().config.help_text
    if v == "":
        help_str = '\n'.join([f'help {key}\t{help_text[key][0]}' for key in help_text])
        await help.finish(help_str)
    else:
        if not help_text.get(v):
            await help.finish("没救了")
        else:
            with open(f"{help_folder}{help_text[v][1]}", "r", encoding="UTF-8") as f:
                await help.finish(Message([{
                    "type": "image",
                    "data": {
                        "file": f"base64://{str(image_to_base64(text_to_image(f.read())), encoding='utf-8')}"
                    }
                }]))


ciyun = on_command("词云")


@ciyun.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    argv = str(event.get_message()).strip().split(" ")
    if len(argv) > 2 or (len(argv) == 1 and len(argv[0]) == 0):
        await ciyun.finish("命令格式为\n词云 <日期>\n词云 <开始日期> <结束日期>\n日期格式为yyyymmdd(如20220301)")
        return
    for arg in argv:
        try:
            datetime.strptime(arg, "%Y%m%d")
        except ValueError:
            await ciyun.send("请检查日期格式(yyyymmdd)")
            return
    if len(argv) == 1:
        record_files = fetch_records(record_folder, argv[0])
    else:
        record_files = fetch_records(record_folder, argv[0], argv[1])

    if record_files:
        await ciyun.send("正在生成...")
    else:
        await ciyun.send("无查询记录")
        return

    result_wc = wordcloud_generate(record_files)
    await ciyun.finish(
        MessageSegment.image(f"base64://{str(image_to_base64(wc_to_image(result_wc)), encoding='utf-8')}"))


alias_acg = []
alias_acg_prefix = ['来点', '我要', '我要看', '我要康', '']
alias_acg_suffix = ['老婆', '二次元', '二刺螈', '二次元图', '二刺螈图', '好康的']
for p in alias_acg_prefix:
    for s in alias_acg_suffix:
        alias_acg.append(f"{p}{s}")
acg = on_command("acg", aliases=set(alias_acg), rule=to_me())


@acg.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    img_bytes = requests.get('http://api.mtyqx.cn/api/random.php').content
    await acg.finish(MessageSegment.image(f"base64://{str(bytes_to_base64(img_bytes), encoding='utf-8')}"))


sticker = on_command("#")


@sticker.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    argv = str(event.get_message()).strip().split(" ")
    if argv[0] == "ongeki":
        img = random.choice(os.listdir(ongeki_sticker_folder))
        await sticker.finish(MessageSegment.image("file:///" + os.path.abspath(f"{ongeki_sticker_folder}{img}")))


question = on_regex(r".*？$", rule=to_me())


@question.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    await question.finish(MessageSegment.image(f"file:///{os.path.abspath(f'{poke_img_folder}waritodoudemoii.jpg')}"))


djw = on_command("对吗？", aliases={"对。。对吗？", "哦对的对的", "哦不对不对", "哎呀不对"})


@djw.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    djw_dir = f"{audio_folder}djw/"
    djw_audio = random.choice(os.listdir(djw_dir))
    print(f"{djw_dir}{djw_audio}")
    await djw.finish(MessageSegment.record(f"file:///{os.path.abspath(f'{djw_dir}{djw_audio}')}"))


sb = on_regex(r"^(傻逼)$")


@sb.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    msg = MessageSegment.reply(event.message_id)
    if event.to_me:
        msg += MessageSegment.image(f"file:///{os.path.abspath(f'{poke_img_folder}sorena.jpg')}")
    else:
        msg += MessageSegment.image(f"file:///{os.path.abspath(f'{general_sticker_folder}sb.jpg')}")
    await sb.finish(msg)


sbsb = on_regex(r"^(傻宝)$")


@sbsb.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    await sbsb.finish(MessageSegment.reply(event.message_id)
                      + MessageSegment.image(f"file:///{os.path.abspath(f'{general_sticker_folder}sbsb.jpg')}"))


add_food = on_command('添加食物', rule=to_me())
food_num = len(os.listdir(food_folder))


@add_food.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    msgs = event.get_message()
    global food_num
    tmp_food_num = food_num
    for msg in msgs:
        if msg.type == "image":
            tmp_food_num += 1
            urllib.request.urlretrieve(msg.data['url'], f"{food_folder}{tmp_food_num}.jpg")

    if tmp_food_num != food_num:
        new_food_cnt = tmp_food_num - food_num
        food_num = tmp_food_num
        await add_food.finish(MessageSegment.reply(event.message_id)
                              + MessageSegment.text(f"添加成功！\n添加了{new_food_cnt}种食物，目前共有{food_num}种食物。"))
    else:
        await add_food.finish(MessageSegment.reply(event.message_id)
                              + MessageSegment.text(f"请添加食物"))


what_to_eat = on_command('whattoeat', aliases={'吃啥', '吃什么', '今天吃什么'}, rule=to_me())


@what_to_eat.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    msg = MessageSegment.reply(event.message_id)

    try:
        num_food_to_get = int(str(event.get_message()).strip())
        if num_food_to_get <= 0:
            raise ValueError
        if num_food_to_get > 3:
            text_seg = MessageSegment.text('少吃点')
            msg = msg + text_seg
            await what_to_eat.send(msg)
            return
    except ValueError:
        num_food_to_get = 1

    foods = random.sample(os.listdir(food_folder), num_food_to_get)
    for food in foods:
        img_path = food_folder + food
        msg += MessageSegment.image('file:///' + os.path.abspath(img_path))

    # 统计吃饭情况
    group_id = event.group_id
    sender_id = event.user_id
    food_dict = shelve.open('src/static/food.db', writeback=True)
    if str(group_id) not in food_dict:
        food_dict[str(group_id)] = {}
    if str(sender_id) not in food_dict[str(group_id)]:
        food_dict[str(group_id)][str(sender_id)] = 0
    food_dict[str(group_id)][str(sender_id)] += 1
    food_dict.close()

    await what_to_eat.finish(msg)


food_stat = on_command('本群吃饭情况', rule=to_me())


@food_stat.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    result = await stat(bot, event.group_id, "src/static/food.db", '吃饭', '顿')
    await food_stat.finish(result)


translate = on_regex(r"[\s\S]+是(啥|什么)意思")


@translate.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: dict):
    regex = r"([\s\S]+)是(啥|什么)意思"
    text = re.match(regex, str(event.get_message())).group(1).strip()
    if len(text) > 500:
        await translate.finish(MessageSegment.image(f"file:///{os.path.abspath(f'{poke_img_folder}waritodoudemoii.jpg')}"))
    else:
        await translate.finish(
            MessageSegment.reply(event.message_id)
            + MessageSegment.text(translate_to_zh(text)))


async def _group_poke(bot: Bot, event: Event, state: dict) -> bool:
    value = (event.notice_type == "notify" and event.sub_type == "poke" and event.target_id == int(bot.self_id))
    return value


poke = on_notice(rule=_group_poke, priority=10, block=True)


async def invoke_poke(group_id, user_id) -> str:
    db = get_driver().config.db
    ret = "default"
    ts = int(time.time())
    c = await db.cursor()
    await c.execute(f"select * from group_poke_table where group_id={group_id}")
    data = await c.fetchone()
    if data is None:
        await c.execute(f'insert into group_poke_table values ({group_id}, {ts}, 1, 0, "default")')
    else:
        t2 = ts
        if data[3] == 1:
            return "disabled"
        if data[4].startswith("limited"):
            duration = int(data[4][7:])
            if ts - duration < data[1]:
                ret = "limited"
                t2 = data[1]
        await c.execute(
            f'update group_poke_table set last_trigger_time={t2}, triggered={data[2] + 1} where group_id={group_id}')
    await c.execute(f"select * from user_poke_table where group_id={group_id} and user_id={user_id}")
    data2 = await c.fetchone()
    if data2 is None:
        await c.execute(f'insert into user_poke_table values ({user_id}, {group_id}, 1)')
    else:
        await c.execute(
            f'update user_poke_table set triggered={data2[2] + 1} where user_id={user_id} and group_id={group_id}')
    await db.commit()
    return ret


@poke.handle()
async def _(bot: Bot, event: Event, state: T_State):
    v = "default"
    group_id = event.__getattribute__('group_id')
    sender_id = event.sender_id
    if group_id is None:
        event.__delattr__('group_id')
    else:
        poke_dict = shelve.open('src/static/poke.db', writeback=True)
        if str(group_id) not in poke_dict:
            poke_dict[str(group_id)] = {}
        if str(sender_id) not in poke_dict[str(group_id)]:
            poke_dict[str(group_id)][str(sender_id)] = 0
        poke_dict[str(group_id)][str(sender_id)] += 1
        poke_dict.close()
        v = await invoke_poke(event.group_id, event.sender_id)
        if v == "disabled":
            await poke.finish()
            return
    r = randint(1, 20)
    if v == "limited":
        await poke.send(Message([{
            "type": "poke",
            "data": {
                "qq": f"{event.sender_id}"
            }
        }]))
    elif r <= 2:
        await poke.send(Message([{
            "type": "record",
            "data": {
                "file": "file:///" + os.path.abspath("src/static/mai/poke/voice/youkemoshima.mp3")
            }
        }]))
    elif 2 < r <= 15:
        await poke.send(Message([{
            "type": "image",
            "data": {
                "file": "file:///" + os.path.abspath(f"{poke_img_folder}{random.choice(os.listdir(poke_img_folder))}")
            }
        }]))
    else:
        info = await bot.get_group_member_info(group_id=group_id, user_id=sender_id)
        print(info)
        name = info['card']
        if name == '':
            name = info['nickname']
        name = name.replace('[', ' ').replace(']', ' ').replace('&', ' ')
        talk = random.choice(
             [f'我真是怀疑你闲的程度啊，{name}',
              f'你是不是有病啊，{name}',
              f'{name}，有病吧',
              f'感谢{name}的舰长',
              f'{name}你带我走吧，{name}，啊啊{name}，{name}',
              # '哼，哼，啊啊，啊啊啊，啊啊啊啊！',
              f'{name}，我真的好喜欢你啊！木啊！为了你，我要听猫中毒！'
              ])
        # msg = CQMsg['tts'].format(talk)
        await poke.send(Message([{
            "type": "tts",
            "data": {
                "text": f"{talk}"
            }
        }]))


async def send_poke_stat(group_id: int, bot: Bot):
    poke_dict = shelve.open('src/static/poke.db')
    if str(group_id) not in poke_dict:
        poke_dict.close()
        return
    else:
        group_stat = poke_dict[str(group_id)]
        poke_dict.close()
        sorted_dict = {k: v for k, v in sorted(group_stat.items(), key=lambda item: item[1], reverse=True)}
        index = 0
        data = []
        for k in sorted_dict:
            data.append((k, sorted_dict[k]))
            index += 1
            if index == 3:
                break
        await bot.send_msg(group_id=group_id, message="接下来公布一下我上次失忆以来，本群最闲着没事干玩戳一戳的人")
        await asyncio.sleep(1)
        if len(data) == 3:
            await bot.send_msg(group_id=group_id, message=Message([
                {"type": "text", "data": {"text": "第三名，"}},
                {"type": "at", "data": {"qq": f"{data[2][0]}"}},
                {"type": "text", "data": {"text": f"，一共戳了我{data[2][1]}次，这就算了"}},
            ]))
            await asyncio.sleep(1)
        if len(data) >= 2:
            await bot.send_msg(group_id=group_id, message=Message([
                {"type": "text", "data": {"text": "第二名，"}},
                {"type": "at", "data": {"qq": f"{data[1][0]}"}},
                {"type": "text", "data": {"text": f"，一共戳了我{data[1][1]}次，也太几把闲得慌了，建议多戳戳自己肚皮"}},
            ]))
            await asyncio.sleep(1)
        await bot.send_msg(group_id=group_id, message=Message([
            {"type": "text", "data": {"text": "最JB离谱的第一名，"}},
            {"type": "at", "data": {"qq": f"{data[0][0]}"}},
            {"type": "text", "data": {"text": f"，一共戳了我{data[0][1]}次，就那么喜欢听我骂你吗"}},
        ]))


poke_stat = on_command("本群戳一戳情况", rule=to_me())


@poke_stat.handle()
async def _(bot: Bot, event: Event, state: T_State):
    group_id = event.group_id
    await send_poke_stat(group_id, bot)


poke_setting = on_command("戳一戳设置")


@poke_setting.handle()
async def _(bot: Bot, event: Event, state: T_State):
    db = get_driver().config.db
    group_members = await bot.get_group_member_list(group_id=event.group_id)
    for m in group_members:
        if m['user_id'] == event.user_id:
            break
    su = get_driver().config.superusers
    if m['role'] != 'owner' and m['role'] != 'admin' and str(m['user_id']) not in su:
        await poke_setting.finish("只有管理员可以设置戳一戳")
        return
    argv = str(event.get_message()).strip().split(' ')
    try:
        if argv[0] == "默认":
            c = await db.cursor()
            await c.execute(
                f'update group_poke_table set disabled=0, strategy="default" where group_id={event.group_id}')
        elif argv[0] == "限制":
            c = await db.cursor()
            await c.execute(
                f'update group_poke_table set disabled=0, strategy="limited{int(argv[1])}" where group_id={event.group_id}')
        elif argv[0] == "禁用":
            c = await db.cursor()
            await c.execute(
                f'update group_poke_table set disabled=1 where group_id={event.group_id}')
        else:
            raise ValueError
        await poke_setting.send("设置成功")
        await db.commit()
    except (IndexError, ValueError):
        await poke_setting.finish(
            "命令格式：\n戳一戳设置 默认   将启用默认的戳一戳设定\n戳一戳设置 限制 <秒>   在戳完一次bot的指定时间内，调用戳一戳只会让bot反过来戳你\n戳一戳设置 禁用   将禁用戳一戳的相关功能")
    pass


random_choice = on_command("帮我选", rule=to_me(), priority=5)


@random_choice.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    argv = str(event.get_message()).strip().split(" ")
    if len(argv) < 2:
        await random_choice.finish("选项不足捏")
        return
    r = random.random()
    p = 0.1919810
    if r <= p:
        await random_choice.finish(MessageSegment.image(f"file:///{os.path.abspath(f'{poke_img_folder}waritodoudemoii.jpg')}"))
    else:
        await random_choice.finish(
            MessageSegment.reply(event.message_id)
            + MessageSegment.text(f"建议选择“{random.choice(argv)}”"))


random_person = on_regex("随个([男女]?)人", priority=1)


@random_person.handle()
async def _(bot: Bot, event: Event, state: T_State):
    try:
        gid = event.group_id
        glst = await bot.get_group_member_list(group_id=gid, self_id=int(bot.self_id))
        v = re.match("随个([男女]?)人", str(event.get_message())).group(1)
        if v == '男':
            for member in glst[:]:
                if member['sex'] != 'male':
                    glst.remove(member)
        elif v == '女':
            for member in glst[:]:
                if member['sex'] != 'female':
                    glst.remove(member)
        m = random.choice(glst)
        await random_person.finish(Message([{
            "type": "at",
            "data": {
                "qq": event.user_id
            }
        }, {
            "type": "text",
            "data": {
                "text": f"\n{m['card'] if m['card'] != '' else m['nickname']}({m['user_id']})"
            }
        }]))

    except AttributeError:
        await random_person.finish("请在群聊使用")


snmb = on_regex("随个.+", priority=5)


@snmb.handle()
async def _(bot: Bot, event: Event, state: T_State):
    try:
        gid = event.group_id
        if random.random() < 0.3:
            await snmb.finish(Message([
                {"type": "text", "data": {"text": "随你"}},
                {"type": "image", "data": {"file": "https://www.diving-fish.com/images/emoji/horse.png"}}
            ]))
        else:
            glst = await bot.get_group_member_list(group_id=gid, self_id=int(bot.self_id))
            m = random.choice(glst)
            await random_person.finish(Message([{
                "type": "at",
                "data": {
                    "qq": event.user_id
                }
            }, {
                "type": "text",
                "data": {
                    "text": f"\n{m['card'] if m['card'] != '' else m['nickname']}({m['user_id']})"
                }
            }]))
    except AttributeError:
        await random_person.finish("请在群聊使用")


shuffle = on_command('shuffle')


@shuffle.handle()
async def _(bot: Bot, event: Event):
    argv = int(str(event.get_message()))
    if argv > 100:
        await shuffle.finish('请输入100以内的数字')
        return
    d = [str(i + 1) for i in range(argv)]
    random.shuffle(d)
    await shuffle.finish(','.join(d))


repeat_and_record = on_message(priority=20)
repeat_dict = defaultdict(list)


@repeat_and_record.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    group_id = event.group_id
    # repeat
    repeat_list = repeat_dict[str(group_id)]
    if len(repeat_list) == 0:
        repeat_list.append('')
        repeat_list.append(False)
    msg = event.get_message()
    p = 0.0114514
    if repeat_list[0] == msg and not repeat_list[1]:
        p = 1
    elif repeat_list[0] != msg and repeat_list[1]:
        repeat_list[0] = msg
        repeat_list[1] = False
    elif repeat_list[0] != msg:
        repeat_list[0] = msg
    r = random.random()
    if r <= p:  # 0.0114514 default
        repeat_list[1] = True
        await repeat_and_record.send(msg)

    # record
    if group_id != 879106299:
        return
    if event.user_id in [3419099188, 507985595, 848581150]:
        return
    msg = event.get_message().extract_plain_text().strip()
    if len(msg) == 0:
        return
    stop_msg_regex = r"(^今日舞萌$)|(^查歌)|(^分数线)|^([绿黄红紫白]?)id([0-9]+)$|(是什么歌$)|(^b50$)|(^成分查询)|(^小亮)"
    if re.match(stop_msg_regex, msg):
        return
    # re_non_text = re.compile(r"\[(CQ.*)\] ")
    # msg = re_non_text.sub("", msg)
    write_path = f"{record_folder}{datetime.now(SH).strftime('%Y%m%d')}.txt"
    mode = 'a' if os.path.exists(write_path) else 'w'
    with open(write_path, mode) as f:
        f.write(f"{msg}\n")


status = on_command("status", permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER, block=True)


@status.handle()
async def _(bot: Bot, event: Event, state: T_State):
    try:
        py_info = platform.python_version()
        pla = platform.platform()
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory().percent
        memory = round(memory, 2)
        disk = psutil.disk_usage('/').percent
    except Exception:  # ignore
        await status.finish("获取状态失败")
        return

    msg = ""

    if cpu > 80 or memory > 80 or disk > 80:
        ex_msg = "蚌埠住了..."
    else:
        ex_msg = "一般"

    msg += "server status:\n"
    msg += f"OS: {pla}"
    msg += f"Running on Python {py_info}\n"
    msg += f"CPU {cpu}%\n"
    msg += f"MEM {memory}%\n"
    msg += f"DISK {disk}%\n"
    msg += ex_msg
    await status.finish(msg)


reset = on_command("reset", priority=0, rule=to_me(), permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER, block=True)


@reset.handle()
async def _(bot: Bot, event: Event, state: dict):
    await reset.send(Message([{
        "type": "image",
        "data": {
            "file": "file:///" + os.path.abspath("src/static/mai/pic/meimeireset.png")
        }
    }]))

    os.execl(sys.executable, sys.executable, *sys.argv)


shut_up = on_command("shut up", priority=0, rule=to_me(), permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER, block=True)


@shut_up.handle()
async def _(bot: Bot, event: Event, state: dict):
    await shut_up.send(Message([{
        "type": "image",
        "data": {
            "file": "file:///" + os.path.abspath("src/static/mai/pic/xiaoshi.jpg")
        }
    }]))

    sys.exit(0)

# taro_lst = []
#
# with open('src/static/taro.txt', encoding='utf-8') as f:
#     for line in f:
#         elem = line.strip().split('\t')
#         taro_lst.append(elem)
#
#
# taro = on_regex("溜冰塔罗牌")
#
#
# @taro.handle()
# async def _(bot: Bot, event: Event):
#     group_id = event.group_id
#     nickname = event.sender.nickname
#     if str(group_id) != "702156482":
#         return
#     c = randint(0, 10)
#     a = randint(0, 1)
#     s1 = "正位" if a == 0 else "逆位"
#     s2 = taro_lst[c][3 + a]
#     await taro.finish(f"来看看{ nickname }抽到了什么：\n{taro_lst[c][0]}（{taro_lst[c][1]}，{taro_lst[c][2]}）{s1}：\n{s2}")
