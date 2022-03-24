import os
import random
import hashlib
import requests

from dotenv import load_dotenv


# 获取百度翻译api的APP ID和密钥
load_dotenv()
app_id = os.getenv('APP_ID')
app_key = os.getenv('APP_KEY')


def translate_to_zh(q: str):
    # 生成调用参数
    hl = hashlib.md5()
    salt = str(random.randint(114514, 1919810))
    sign = app_id + q + salt + app_key
    hl.update(sign.encode(encoding='utf-8'))
    sign = hl.hexdigest()
    res = requests.get(
        f"http://api.fanyi.baidu.com/api/trans/vip/translate?q={q}&from=auto&to=zh&appid={app_id}&salt={salt}&sign={sign}").json()
    # 提取翻译结果(多段文本会返回多段文字)
    return "\n".join([result['dst'] for result in res['trans_result']])

