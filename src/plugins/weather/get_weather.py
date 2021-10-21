from nonebot.log import logger
from httpx import AsyncClient
import nonebot

apikey = nonebot.get_driver().config.heweather_apikey
if not apikey:
    raise ValueError(f"请在环境变量中添加 heweather_apikey 参数")
url_weather_api = "https://devapi.qweather.com/v7/weather/"
url_geoapi = "https://geoapi.qweather.com/v2/city/"


# # 获取城市ID
# async def get_location(city_kw: str, api_type: str = "lookup") -> dict:
#     async with AsyncClient() as client:
#         res = await client.get(
#             url_geoapi + api_type, params={"location": city_kw, "key": apikey}
#         )
#         return res.json()


# 获取天气信息
async def get_weather(api_type: str, city_id: str) -> dict:
    async with AsyncClient() as client:
        res = await client.get(
            url_weather_api + api_type, params={"location": city_id, "key": apikey},
            timeout=30
        )
        return res.json()


# 获取天气灾害预警
async def get_weather_warning(city_id: str) -> dict:
    async with AsyncClient() as client:
        res = await client.get(
            "https://devapi.qweather.com/v7/warning/now",
            params={"location": city_id, "key": apikey},
            timeout=30
        )
        res = res.json()
    return res if res["code"] == "200" and res["warning"] else None


# 获取空气质量信息
async def get_weather_air(city_id: str):
    async with AsyncClient() as client:
        res = await client.get(
            "https://devapi.qweather.com/v7/air/now?",
            params={"location": city_id, "key": apikey},
            timeout=30
        )
        return res.json()


async def get_city_weather(city: str):
    # global city_id
    # city_info = await get_Location(city)
    # logger.debug(city_info)
    if True:  # city_info["code"] == "200":
        city_id = "101010100"  # city_info["location"][0]["id"]
        city_name = "北京"  # city_info["location"][0]["name"]

        # # 3天天气
        # daily_info = await get_WeatherInfo("3d", city_id)
        # daily = daily_info["daily"]
        # day1 = daily[0]
        # day2 = daily[1]
        # day3 = daily[2]

        # 实时天气
        now_info = await get_weather("now", city_id)
        if now_info["code"] == "200":
            now = now_info["now"]
        else:
            return int(now_info["code"])

        # 空气质量
        air_info = await get_weather_air(city_id)
        air = air_info["now"]
        if air_info["code"] != "200":
            return int(air_info["code"])

        # 天气预警信息
        warning = await get_weather_warning(city_id)

        return {
            "city": city_name,
            "now": now,
            "air": air,
            "warning": warning,
        }
    # else:
    #     logger.error(
    #         f"错误: {city_info['code']} 请参考 https://dev.qweather.com/docs/start/status-code/ "
    #     )
    #     return int(city_info["code"])
