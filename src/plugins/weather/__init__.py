import nonebot
from nonebot.adapters.cqhttp import Message, MessageEvent, Bot, MessageSegment
from nonebot import on_command, on_message, on_notice, require, get_driver, on_regex

from .get_weather import get_city_weather


weather = on_command('出勤天气', priority=1)

@weather.handle()
async def _(bot: Bot, event: MessageEvent):
    # city = get_msg(event.get_plaintext())
    # if city is None:
    #     await weather.finish("地点是...空气吗?? >_<")
    data = await get_city_weather("")
    nonebot.logger.log(data)
    if type(data) is int:
        if data == 404:
            await weather.finish("未找到城市")
        else:
            await weather.finish(f"错误代码={data}")
    wea_msg = "城市: " + data["city"] + "\n气温: " + data["now"]["temp"] + "°C" + "\n体感温度: " + data["now"]["feelsLike"]\
              + "°C" + "\n天气: " + data["now"]["text"] + "\nAQI: " + data["air"]["aqi"] + " " + data["air"]["category"]
    if data["warning"]:
        warning = data["warning"]["warning"]
        text = ""
        for i in range(len(warning)):
            text += f'\n{warning[i]["text"]}'
        await weather.finish(MessageSegment.text(wea_msg) + MessageSegment.text(text))
    else:
        await weather.finish(MessageSegment.text(wea_msg))
