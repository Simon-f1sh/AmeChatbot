import base64
import pytz
from io import BytesIO
from PIL import Image

import nonebot
from nonebot.adapters.cqhttp import Message, MessageEvent, Bot, MessageSegment
from nonebot import on_command, on_message, on_notice, require, get_driver, on_regex, logger
from datetime import datetime, timedelta

from .convrt_pic import draw
from .get_weather import get_city_weather, get_weather_warning

driver = get_driver()

SH = pytz.timezone('Asia/Shanghai')
FMT = '%Y-%m-%dT%H:%M+08:00'
scheduler = require("nonebot_plugin_apscheduler").scheduler


async def auto_warning_check(city_id: str):
    (bot,) = nonebot.get_bots().values()
    warning_data = await get_weather_warning(city_id)
    if warning_data:
        warnings = warning_data['warning']
        for warning in warnings:
            pub_time = warning['pubTime']
            nonebot.logger.info(warning['pubTime'])
            naive = datetime.now(SH).replace(tzinfo=None) - timedelta(minutes=30)
            if naive <= datetime.strptime(pub_time, FMT):
                await bot.send_group_msg(group_id=879106299, message=warning['text'])
    else:
        logger.info("No Warning")


@driver.on_startup
def _():
    scheduler.add_job(
        auto_warning_check,
        trigger='cron',
        minute='0,30',
        args=['101010100']
    )


def img_to_b64(pic: Image.Image) -> str:
    buf = BytesIO()
    pic.save(buf, format="PNG")
    base64_str = base64.b64encode(buf.getbuffer()).decode()
    return "base64://" + base64_str


weather = on_command('天气查询', priority=1)


@weather.handle()
async def _(bot: Bot, event: MessageEvent):
    # city = get_msg(event.get_plaintext())
    # if city is None:
    #     await weather.finish("地点是...空气吗?? >_<")
    data = await get_city_weather("")
    nonebot.logger.info(data)
    if type(data) is int:
        if data == 404:
            await weather.finish("未找到城市")
        else:
            await weather.finish(f"错误代码={data}")
    img = draw(data) if data else None
    b64 = img_to_b64(img) if img else None
    # wea_msg = "城市: " + data["city"] + "\n气温: " + data["now"]["temp"] + "°C" + "\n体感温度: " + data["now"]["feelsLike"]\
    #           + "°C" + "\n天气: " + data["now"]["text"] + "\nAQI: " + data["air"]["aqi"] + " " + data["air"]["category"]
    if data["warning"]:
        warning = data["warning"]["warning"]
        text = ""
        for i in range(len(warning)):
            text += f'\n{warning[i]["text"]}'
        await weather.finish(MessageSegment.image(b64) + MessageSegment.text(text))
    else:
        await weather.finish(MessageSegment.image(b64))
