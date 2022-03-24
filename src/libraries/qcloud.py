import os
import random
import string

import pydub
from urllib import parse
from dotenv import load_dotenv
from qcloud_cos import CosConfig, CosS3Client
from sts.sts import Sts
from nonebot.adapters.cqhttp import MessageSegment
from typing import Dict

from .CONST import mai_tmp_folder

# 配置腾讯api

load_dotenv()
secret_id = os.getenv('SECRET_ID')  # 替换为用户的 SecretId，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
secret_key = os.getenv('SECRET_KEY')  # 替换为用户的 SecretKey，请登录访问管理控制台进行查看和管理，https://console.cloud.tencent.com/cam/capi
region = 'ap-beijing'  # 替换为用户的 region，已创建桶归属的region可以在控制台查看，https://console.cloud.tencent.com/cos5/bucket
bucket_name = "tpz-1254072339"
config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
client = CosS3Client(config)


async def download_music(music_id: str):
    song_id = music_id[1:5].lstrip("0") if len(music_id) == 5 else music_id

    file_name = f"{song_id}.mp3"
    file_path = f'{mai_tmp_folder}{file_name}'
    if not os.path.exists(file_path):
        response = client.download_file(
            Bucket=bucket_name,
            Key=f'sound/{file_name}',
            DestFilePath=file_path
        )
        print(f"Download Response: {response}")
    return file_path


async def music_to_clip(music_path: str):
    music = pydub.AudioSegment.from_mp3(music_path)

    clip_length = 5000
    clip_start_time_min = int(len(music) * 0.1)
    clip_start_time_max = int(len(music) * 0.9 - clip_length)

    if clip_start_time_min >= clip_start_time_max:
        music_clip = music
    else:
        clip_start_time = random.randint(clip_start_time_min, clip_start_time_max)
        music_clip = music[clip_start_time: clip_start_time + clip_length]

    string_set = string.ascii_letters + string.digits
    random_name = "".join(random.sample(string_set, 8)) + ".mp3"
    temp_path = f"{mai_tmp_folder}{random_name}"
    music_clip.export(temp_path)
    return f"file:///{os.path.abspath(temp_path)}", temp_path


async def download_music_and_to_clip(song_id: str):
    file_path = await download_music(song_id)
    temp_url, temp_path = await music_to_clip(os.path.abspath(file_path))
    if os.path.exists(file_path):
        os.remove(file_path)
    return temp_url, temp_path


async def download_music_and_get_length(song_id: str):
    file_path = await download_music(song_id)
    music = pydub.AudioSegment.from_mp3(file_path)
    length = len(music) / 1000
    if os.path.exists(file_path):
        os.remove(file_path)
    return length


async def search_audio(music: Dict):
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
