import asyncio
import math
import re
import shelve
import time
import random
from collections import defaultdict

from nonebot import on_command, on_message, on_notice, get_driver, on_regex, logger
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Message, Event, Bot, MessageSegment, PrivateMessageEvent
from typing import Dict, Tuple

from .word_list import word_list
from src.libraries.image import text_to_image, image_to_base64

quiz_dict: Dict[Tuple[str, str], list] = {}
quiz_cd_dict: Dict[Tuple[str, str], float] = {}
word_dict: Dict[Tuple[str, str], dict] = {}

driver = get_driver()


@driver.on_startup
def _():
    logger.info("Load help text successfully")
    help_text: dict = get_driver().config.help_text
    help_text['xuexi'] = ('查看日语相关功能', """19岁，是妹妹。
可用命令如下：
大佐测试/我想学日语/我要学日语    日语词汇测试
错词表<页数>    查看错词表(页数不填默认第一页)
复习    从错词表中抽词测试，仅在私聊可用
不学了/结束    结束当前测试
测试设置 启用/禁用    启用/禁用功能""")


async def _quiz_status(bot: Bot, event: Event, state: dict) -> bool:
    group_id = event.group_id
    mt = "group"
    if group_id is None:
        mt = "private"
    k = (mt, str(event.sender_id) if mt == "private" else str(group_id))
    if k in word_dict:
        value = (event.notice_type == "notify"
                 and event.sub_type == "poke"
                 and event.target_id == int(bot.self_id)
                 and word_dict[k]['is_end'])
        return value
    return False

quiz = on_regex(r"^(我想学日语|我要学日语|大佐测试)$", block=True)
quiz_solve = on_message(priority=20)
unfamiliar = on_notice(rule=_quiz_status, priority=5, block=True)
vocab_view = on_regex(r"^(错词表)([0-9]*)$", block=True)
review = on_regex(r"^(复习)$", block=True)
end = on_regex(r"^(不学了|结束)$", block=True)
disable_quiz = on_command('测试设置', priority=0)


@unfamiliar.handle()
async def _(bot: Bot, event: Event, state: T_State):
    group_id = event.group_id
    sender_id = event.sender_id
    mt = "group"
    k = (mt, str(group_id))
    if group_id is None:
        event.__delattr__('group_id')
        mt = "private"
        k = (mt, str(sender_id))

    word = word_dict[k]['jap']
    vocab_dict = shelve.open('src/static/vocab.db', writeback=True)
    if str(sender_id) not in vocab_dict:
        vocab_dict[str(sender_id)] = defaultdict(int)
    vocab_dict[str(sender_id)][word] += 2
    vocab_dict.close()
    if group_id is None:
        await unfamiliar.send(Message("收到"))
    # del word_dict[k]
    # await asyncio.sleep(2)
    # state["k"] = k
    # asyncio.create_task(quiz_task(bot, event, state))


@disable_quiz.handle()
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
        await disable_quiz.finish("只有管理员可以设置测试")
        return
    db = get_driver().config.db
    c = await db.cursor()

    if arg == '启用':
        await c.execute(f'update quiz_table set enabled=1 where group_id={event.group_id}')
    elif arg == '禁用':
        await c.execute(f'update quiz_table set enabled=0 where group_id={event.group_id}')
    else:
        await disable_quiz.finish("请输入 测试设置 启用/禁用")
    await db.commit()
    await disable_quiz.finish("设置成功")


@review.handle()
async def _(bot: Bot, event: PrivateMessageEvent, state: T_State):
    mt = event.message_type
    k = (mt, str(event.user_id))
    print(k)
    if k in quiz_dict:
        if k in quiz_cd_dict and time.time() > quiz_cd_dict[k] - 300:
            # 如果已经过了 300 秒则自动结束上一次
            del quiz_dict[k]
            del word_dict[k]
        else:
            await quiz.send("当前已有正在进行的学习进程")
            return

    vocab_dict = shelve.open('src/static/vocab.db')
    if str(event.user_id) not in vocab_dict:
        vocab_dict.close()
        await vocab_view.finish("错词表为空")
    vocab_keys = list(vocab_dict[str(event.user_id)].keys())
    vocab_dict.close()
    await quiz.send(
        '我将从错词表里面抽取10个词汇进行测试，每个单词请在15s内答出中文释义，不会的单词在公布答案后可在10s内戳一戳来加入错词表(可重复添加来记录错误次数)')
    await quiz.send(
        '复习测试中，如果同样的单词答对两遍，该单词在错词表中的错误次数将会-1')
    await asyncio.sleep(5)

    quiz_dict[k] = random.sample(vocab_keys, min(10, len(vocab_keys)))
    state["k"] = k
    quiz_cd_dict[k] = time.time() + 600
    asyncio.create_task(quiz_task(bot, event, state, is_review=True))


def to_chinese_pattern(string:str) -> str:
    new_string = ''
    for i in string:
        codes = ord(i)  # 将字符转为ASCII或UNICODE编码
        if codes <= 126:  # 若是半角字符
            new_string = new_string + chr(codes + 65248)  # 则转为全角
        else:
            new_string = new_string + i  # 若是全角，则不转换
    return new_string


@vocab_view.handle()
async def _(bot: Bot, event: Event, state: T_State):
    vocab_dict = shelve.open('src/static/vocab.db')
    uid = event.get_user_id()
    if str(uid) not in vocab_dict:
        vocab_dict.close()
        await vocab_view.finish("错词表为空")
    else:
        regex = r"错词表([0-9]*)"
        res = re.match(regex, str(event.get_message()).lower())
        page = 1
        try:
            if res.group(1) != "":
                page = int(res.group(1))
        except Exception as e:
            print("Exception" + str(e))
            vocab_dict.close()
            await vocab_view.finish("命令错误，请检查语法")

        if page < 1:
            vocab_dict.close()
            return

        vocab_stat = sorted(vocab_dict[str(uid)].items(), key=lambda item: item[1], reverse=True)
        vocab_dict.close()
        length = len(vocab_stat)
        page_len = 25
        pages = math.ceil(length / page_len)
        if page > pages:
            return
        reply_text = f"错误次数{'　' * 2}日文(假名){'　' * 16}类型{'　' * 6}中文\n{'—' * 50}\n"
        for i in range((page - 1) * page_len, min(page * page_len, length)):
            detail = word_list[vocab_stat[i][0]]
            times = to_chinese_pattern(str(math.ceil(vocab_stat[i][1] / 2)))
            jap = detail['jap']
            hira = detail['hira']
            word_type = to_chinese_pattern(detail['type'])
            chn = '，'.join(detail['chn'])
            reply_text += f"{times}{'　' * (6 - len(times))}{jap}({hira}){'　' * (20 - len(jap) - len(hira))}{word_type}{'　' * (8 - len(word_type))}{chn}\n"
        reply_text += f"{'—' * 50}\n{page}/{pages}页"

        if event.message_type == "private":
            await vocab_view.finish(MessageSegment.image(f"base64://{str(image_to_base64(text_to_image(reply_text)), encoding='utf-8')}"))
        await vocab_view.finish(MessageSegment.reply(event.message_id)
                                + MessageSegment.image(f"base64://{str(image_to_base64(text_to_image(reply_text)), encoding='utf-8')}"))


async def quiz_task(bot: Bot, event: Event, state: T_State, is_review: bool):
    k = state["k"]
    if len(quiz_dict[k]) == 0:
        del quiz_dict[k]
        asyncio.create_task(bot.send(event, "测试结束"))
        return
    word_dict[k] = word_list[quiz_dict[k].pop()]
    word_dict[k]['is_end'] = False
    word_dict[k]['is_review'] = is_review
    word = word_dict[k]
    print(word)
    asyncio.create_task(bot.send(event, f"{word['hira']}"))
    await asyncio.sleep(15)
    if word['is_end']:
        return
    word['is_end'] = True
    asyncio.create_task(bot.send(event, f"正确答案是：{'，'.join(word['chn'])}"))
    await asyncio.sleep(10)
    if k in word_dict:
        del word_dict[k]
        asyncio.create_task(quiz_task(bot, event, state, is_review=is_review))


@quiz_solve.handle()
async def _(bot: Bot, event: Event, state: T_State):
    mt = event.message_type
    k = (mt, str(event.user_id) if mt == "private" else str(event.group_id))
    if k in word_dict:
        if word_dict[k]['is_end']:
            return
        ans = str(event.get_message())
        if ans in word_dict[k]['chn']:
            word_dict[k]['is_end'] = True
            is_review = word_dict[k]['is_review']
            word = word_dict[k]['jap']
            del word_dict[k]
            if is_review:
                vocab_dict = shelve.open('src/static/vocab.db', writeback=True)
                vocab_dict[str(event.user_id)][word] -= 1
                if vocab_dict[str(event.user_id)][word] == 0:
                    vocab_dict[str(event.user_id)].pop(word)
                if not vocab_dict[str(event.user_id)]:
                    vocab_dict.pop(str(event.user_id))
                vocab_dict.close()
            if mt == "private":
                await quiz_solve.send("正解")
            else:
                await quiz_solve.send(MessageSegment.reply(event.message_id) + MessageSegment.text("正解"))
            await asyncio.sleep(2)
            state["k"] = k
            asyncio.create_task(quiz_task(bot, event, state, is_review=is_review))


@quiz.handle()
async def _(bot: Bot, event: Event, state: T_State):
    mt = event.message_type
    k = (mt, str(event.user_id) if mt == "private" else str(event.group_id))
    print(k)
    if mt == "group":
        gid = event.group_id
        db = get_driver().config.db
        c = await db.cursor()
        await c.execute(f"select * from quiz_table where group_id={gid}")
        data = await c.fetchone()
        if data is None:
            await c.execute(f'insert into quiz_table values ({gid}, 1)')
        elif data[1] == 0:
            await quiz.finish("本群已禁用日语测试")
            return
    if k in quiz_dict:
        if k in quiz_cd_dict and time.time() > quiz_cd_dict[k] - 300:
            # 如果已经过了 300 秒则自动结束上一次
            del quiz_dict[k]
            del word_dict[k]
        else:
            await quiz.send("当前已有正在进行的学习进程")
            return

    await quiz.send(
        '我将从词库里面抽取10个词汇进行测试，每个单词请在15s内答出中文释义，不会的单词在公布答案后可在10s内戳一戳来加入错词表(可重复添加来记录错误次数)')
    if mt == "group":
        await quiz.send(
            '为防止刷屏，群聊中戳一戳加入错词表不会有实际反馈，没有反戳或者发表情包就算加入成功')
    await asyncio.sleep(5)
    quiz_dict[k] = random.sample(list(word_list.keys()), 10)
    state["k"] = k
    quiz_cd_dict[k] = time.time() + 600
    asyncio.create_task(quiz_task(bot, event, state, is_review=False))


@end.handle()
async def _(bot: Bot, event: Event, state: T_State):
    mt = event.message_type
    k = (mt, str(event.user_id) if mt == "private" else str(event.group_id))
    print(k)
    if k in quiz_dict:
        word_dict[k]['is_end'] = True
        del word_dict[k]
        del quiz_dict[k]
        await end.finish("收到")
