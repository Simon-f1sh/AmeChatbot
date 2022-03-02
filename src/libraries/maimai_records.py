import math
import os
import aiohttp
from typing import Optional, Tuple
from PIL import Image
from dotenv import load_dotenv

from .image import text_to_image

load_dotenv()
developer_token = os.getenv('DEVELOPER_TOKEN')


async def get_records_by_level_or_ds(page: int, qq: str, username: Optional[str] = "", level: str = None, ds: str = None) -> Tuple[Optional[Image.Image], int]:
    if username == "":
        username, status = await get_username(qq)
        if status != 200:
            return None, status
    async with aiohttp.request("GET",
                               f"https://www.diving-fish.com/api/maimaidxprober/dev/player/records?username={username}",
                               headers={"developer-token": developer_token}) as resp:
        if resp.status == 400:
            return None, 400
        records = await resp.json()

        if level:
            filtered_records = sorted(list(filter(lambda song: song['level'] == level, records['records'])),
                                      key=lambda song: song['achievements'], reverse=True)
            text = f"你的{level}分数列表(从高到低):\n"
        elif ds:
            filtered_records = sorted(list(filter(lambda song: song['ds'] == float(ds), records['records'])),
                                      key=lambda song: song['achievements'], reverse=True)
            text = f"你的{ds}分数列表(从高到低):\n"
        else:
            return None, -1

        records_len = len(filtered_records)
        index = (page - 1) * 25
        if index >= records_len or index < 0:
            return None, -1

        for i in range(index, min(index + 25, records_len)):
            record = filtered_records[i]
            achievement = format(record['achievements'], '.4f')
            level_label = record['level_label'][0:3].replace('Re:', 'Re:M')
            fc = f"({record['fc'].upper().replace('P', '+').replace('A+', 'AP')})" if record['fc'] != '' else ""
            fs = f"({record['fs'].upper().replace('P', '+')})" if record['fs'] != '' else ""
            text += f"""{achievement}% ({record['type']})({level_label}){record['title']} {fc} {fs}\n"""

        text += f"页数{page}/{math.ceil(records_len / 25)}"

        return text_to_image(text), 200


async def get_username(qq: str) -> Tuple[Optional[str], int]:
    async with aiohttp.request("POST", "https://www.diving-fish.com/api/maimaidxprober/query/player",
                               json={"qq": qq}) as resp:
        if resp.status == 400:
            return None, 400
        if resp.status == 403:
            return None, 403
        data = await resp.json()
        return data['username'], 200
