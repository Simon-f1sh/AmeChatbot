import asyncio
import math
import re
import shelve
import time
import random
from collections import defaultdict

from nonebot import on_command, on_message, on_notice, require, get_driver, on_regex, logger
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters.cqhttp import Message, Event, Bot, MessageSegment, GROUP_ADMIN, GROUP_OWNER, PrivateMessageEvent
from typing import Dict, Tuple

from .word_list import word_list
from src.libraries.image import text_to_image, image_to_base64

quiz_dict: Dict[Tuple[str, str], list] = {}
quiz_cd_dict: Dict[Tuple[str, str], float] = {}
word_dict: Dict[Tuple[str, str], dict] = {}


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

quiz = on_regex(r"^(我想学日语|大佐测试|w)$", block=True)
quiz_solve = on_message(priority=20)
unfamiliar = on_notice(rule=_quiz_status, priority=5, block=True)
vocab_view = on_regex(r"^(错词表)([0-9]*)$", block=True)
review = on_regex(r"^(复习)$", block=True)
end = on_regex(r"^(不学了|结束)$", block=True)


@unfamiliar.handle()
async def _(bot: Bot, event: Event, state: T_State):
    group_id = event.group_id
    sender_id = event.sender_id
    mt = "group"
    if group_id is None:
        event.__delattr__('group_id')
        mt = "private"
        k = (mt, str(sender_id))
        word = word_dict[k]['jap']
        vocab_dict = shelve.open('src/static/vocab.db', writeback=True)
        if str(sender_id) not in vocab_dict:
            vocab_dict[str(sender_id)] = defaultdict(int)
        vocab_dict[str(sender_id)][word] += 1
        vocab_dict.close()
        await unfamiliar.send(Message("收到"))
        # del word_dict[k]
        # await asyncio.sleep(2)
        # state["k"] = k
        # asyncio.create_task(quiz_task(bot, event, state))
    else:
        k = (mt, str(group_id))
        print(k, "Not Implemented")


@review.handle()
async def _(bot: Bot, event: PrivateMessageEvent, state: T_State):
    mt = event.message_type
    k = (mt, str(event.user_id))
    if k in quiz_dict:
        if k in quiz_cd_dict and time.time() > quiz_cd_dict[k] - 400:
            # 如果已经过了 200 秒则自动结束上一次
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
        '我将从错词表里面抽取10个词汇进行测试，每个单词请在10s内答出中文释义，不会的单词在公布答案后可在5s内戳一戳来加入错词表(可重复添加来记录错误次数)')
    await asyncio.sleep(5)

    quiz_dict[k] = random.sample(vocab_keys, min(10, len(vocab_keys)))
    state["k"] = k
    quiz_cd_dict[k] = time.time() + 600
    asyncio.create_task(quiz_task(bot, event, state))


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
            times = to_chinese_pattern(str(vocab_stat[i][1]))
            jap = detail['jap']
            hira = detail['hira']
            word_type = to_chinese_pattern(detail['type'])
            chn = '，'.join(detail['chn'])
            reply_text += f"{times}{'　' * (6 - len(times))}{jap}({hira}){'　' * (20 - len(jap) - len(hira))}{word_type}{'　' * (8 - len(word_type))}{chn}\n"
        reply_text += f"{'—' * 50}\n{page}/{pages}页"
        await vocab_view.finish(MessageSegment.image(f"base64://{str(image_to_base64(text_to_image(reply_text)), encoding='utf-8')}"))


async def quiz_task(bot: Bot, event: Event, state: T_State):
    k = state["k"]
    if len(quiz_dict[k]) == 0:
        del quiz_dict[k]
        return
    word_dict[k] = word_list[quiz_dict[k].pop()]
    word_dict[k]['is_end'] = False
    word = word_dict[k]
    print(word)
    asyncio.create_task(bot.send(event, f"{word['hira']}"))
    await asyncio.sleep(10)
    if word['is_end']:
        return
    word['is_end'] = True
    asyncio.create_task(bot.send(event, f"正确答案是：{'，'.join(word['chn'])}"))
    await asyncio.sleep(5)
    if k in word_dict:
        del word_dict[k]
        asyncio.create_task(quiz_task(bot, event, state))


@quiz_solve.handle()
async def _(bot: Bot, event: PrivateMessageEvent, state: T_State):
    mt = event.message_type
    k = (mt, str(event.user_id))
    if k in word_dict:
        if word_dict[k]['is_end']:
            return
        ans = str(event.get_message())
        if ans in word_dict[k]['chn']:
            word_dict[k]['is_end'] = True
            del word_dict[k]
            await quiz_solve.send("正解")
            await asyncio.sleep(2)
            state["k"] = k
            asyncio.create_task(quiz_task(bot, event, state))


@quiz.handle()
async def _(bot: Bot, event: PrivateMessageEvent, state: T_State):
    mt = event.message_type
    k = (mt, str(event.user_id))
    print(k)
    if k in quiz_dict:
        if k in quiz_cd_dict and time.time() > quiz_cd_dict[k] - 400:
            # 如果已经过了 200 秒则自动结束上一次
            del quiz_dict[k]
            del word_dict[k]
        else:
            await quiz.send("当前已有正在进行的学习进程")
            return

    await quiz.send(
        '我将从词库里面抽取10个词汇进行测试，每个单词请在10s内答出中文释义，不会的单词在公布答案后可在5s内戳一戳来加入错词表(可重复添加来记录错误次数)')
    await asyncio.sleep(5)
    quiz_dict[k] = random.sample(list(word_list.keys()), 10)
    state["k"] = k
    quiz_cd_dict[k] = time.time() + 600
    asyncio.create_task(quiz_task(bot, event, state))


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
