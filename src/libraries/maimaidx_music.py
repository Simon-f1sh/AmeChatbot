import json
import random
from typing import Dict, List, Optional, Union, Tuple, Any
from copy import deepcopy
import pytz
import requests
from datetime import datetime

from .qcloud import download_music_and_get_length


SH = pytz.timezone('Asia/Shanghai')


def cross(checker: List[Any], elem: Optional[Union[Any, List[Any]]], diff):
    ret = False
    diff_ret = []
    if not elem or elem is Ellipsis:
        return True, diff
    if isinstance(elem, List):
        for _j in (range(len(checker)) if diff is Ellipsis else diff):
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if __e in elem:
                diff_ret.append(_j)
                ret = True
    elif isinstance(elem, Tuple):
        for _j in (range(len(checker)) if diff is Ellipsis else diff):
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if elem[0] <= __e <= elem[1]:
                diff_ret.append(_j)
                ret = True
    else:
        for _j in (range(len(checker)) if diff is Ellipsis else diff):
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if elem == __e:
                diff_ret.append(_j)
                ret = True
    return ret, diff_ret


def in_or_equal(checker: Any, elem: Optional[Union[Any, List[Any]]]):
    if elem is Ellipsis:
        return True
    if isinstance(elem, List):
        return checker in elem
    elif isinstance(elem, Tuple):
        return elem[0] <= checker <= elem[1]
    else:
        return checker == elem


async def search_bpm(bpm: str):
    # 异常处理
    if bpm == '':
        return None, "请输入BPM捏"
    try:
        int(bpm)
    except ValueError:
        return None, "请输入整数BPM捏"

    # 遍历查找
    filtered_list = total_list.filter(bpm=int(bpm))
    if len(filtered_list) == 0:
        return None, "没有找到该BPM的歌捏"

    # 为结果加前缀
    result = f"BPM为{bpm}的歌有："
    for music in filtered_list:
        result += f"\n{music['id']}. {music['title']}"

    return result, ""


async def search_artist(artist: str):
    if len(artist) == 0:
        return None, "请输入曲师捏"
    # 遍历查找
    filtered_list = total_list.filter(artist=artist)

    if len(filtered_list) == 0:
        result = "没有找到该曲师捏"
        probable_artist_list = []
        for listed_artist in artist_list:
            if artist in listed_artist.lower():
                probable_artist_list.append(listed_artist)
        if probable_artist_list:
            result += "。\n您要找的是不是："
            for listed_artist in probable_artist_list:
                result += '\n' + listed_artist
        return None, result
    else:
        result = ""
        real_artist = ""
        for music in filtered_list:
            if music.artist.lower() == artist:
                real_artist = music.artist
                result += f"\n{music['id']}. {music['title']}"
        result = f"曲师{real_artist}写过的歌有：{result}"
        return result, ""


async def search_charter(charter: str):
    if len(charter) == 0:
        return None, "请输入谱师捏"
    if charter == "-":
        return None, "杨教授？"
    # 遍历查找
    filtered_list = total_list.filter(charter=charter)

    if len(filtered_list) == 0:
        result = "没有找到该谱师捏"
        probable_charter_list = []
        for listed_charter in charter_list:
            if charter in listed_charter.lower():
                probable_charter_list.append(listed_charter)
        if probable_charter_list:
            result += '。\n您要找的是不是：'
            for listedCharter in probable_charter_list:
                result += '\n' + listedCharter
        return None, result
    else:
        result = ""
        real_charter = ""
        for music in filtered_list:
            for i in music.diff:
                real_charter = music['charts'][i]['charter']
                musicInfo = music['id'] + '. ' + music['title']
                if i == 2:
                    result += f"\n{musicInfo} Exp"
                elif i == 3:
                    result += f"\n{musicInfo} Mas"
                elif i == 4:
                    result += f"\n{musicInfo} 蕾姆"
        result = f"谱师{real_charter}写过的谱有：{result}"
        return result, ""


async def search_length(music_id: str):
    music = total_list.by_id(music_id)
    if music:
        length = await download_music_and_get_length(music_id)
        result = f'{music_id}. {music.title}\n歌曲长度为{length}秒'
        return result
    return "未找到该歌曲"


async def search_diff(diff_index: int, diff_labels: List[str],  song_id: str):
    if chart_stats.get(song_id):
        stat = chart_stats[song_id][diff_index]
        if not stat.get('tag'):
            return None, "未找到相对难度"
        music = total_list.by_id(song_id)
        return f"""歌曲信息：{music.title} {diff_labels[diff_index]}谱
难度：{stat['tag']}
SSS人数：{stat['sssp_count']}/{stat['count']} ({round(stat['sssp_count'] / stat['count'] * 100, 2)}%)
在同等级歌曲中SSS比例排名：{stat['v'] + 1}/{stat['t']}
平均完成率：{round(stat['avg'], 4)}%
数据更新时间：{update_time}""", ""
    return None, "未找到歌曲"


async def find_rank_with_id(music_id: str, diff_play_count_list: List[List[Any]]):
    diff_rank = 0
    data = None
    for music in diff_play_count_list:
        diff_rank += 1
        if music[0] == music_id:
            data = music
            break
    return diff_rank, data


async def search_pop_rank(diff_labels: List[str], diff_index: int, is_id: bool, music_id_or_rank: Union[str, int]):
    if is_id:
        music_id = music_id_or_rank
        if diff_index:
            diff_rank, data = await find_rank_with_id(music_id, play_count_list[diff_index])
            if data is None:
                return None, "未找到歌曲"
            total_data = (data[0], data[1], diff_index)
            total_rank = play_count_list[5].index(total_data) + 1
            return f"""{data[0]}. {total_list.by_id(data[0]).title}
全{diff_labels[diff_index]}谱热度：{diff_rank}/{len(play_count_list[diff_index])}
全谱面热度：{total_rank}/{len(play_count_list[5])}
游玩人数：{data[1]}
数据更新时间：{update_time}""", ""

        else:
            return None, "请输入难度（绿，黄，红，紫，白）"
    else:
        rank = music_id_or_rank
        if diff_index:
            if rank > len(play_count_list[diff_index]) or rank <= 0:
                return None, "输入有误捏"
            data = play_count_list[diff_index][rank-1]
            total_data = (data[0], data[1], diff_index)
            total_rank = play_count_list[5].index(total_data) + 1
            return f"""{data[0]}. {total_list.by_id(data[0]).title}
全{diff_labels[diff_index]}谱热度：{rank}/{len(play_count_list[diff_index])}
全谱面热度：{total_rank}/{len(play_count_list[5])}
游玩人数：{data[1]}
数据更新时间：{update_time}""", ""

        else:
            if rank > len(play_count_list[5]) or rank <= 0:
                return None, "输入有误捏"

            data = play_count_list[5][rank-1]
            return f"""{data[0]}. {total_list.by_id(data[0]).title} [{diff_labels[data[2]]}]
全谱面热度：{rank}/{len(play_count_list[5])}
游玩人数：{data[1]}
数据更新时间：{update_time}""", ""


class Chart(Dict):
    tap: Optional[int] = None
    slide: Optional[int] = None
    hold: Optional[int] = None
    touch: Optional[int] = None
    brk: Optional[int] = None
    charter: Optional[int] = None

    def __getattribute__(self, item):
        if item == 'tap':
            return self['notes'][0]
        elif item == 'hold':
            return self['notes'][1]
        elif item == 'slide':
            return self['notes'][2]
        elif item == 'touch':
            return self['notes'][3] if len(self['notes']) == 5 else 0
        elif item == 'brk':
            return self['notes'][-1]
        elif item == 'charter':
            return self['charter']
        return super().__getattribute__(item)


class Music(Dict):
    id: Optional[str] = None
    title: Optional[str] = None
    ds: Optional[List[float]] = None
    level: Optional[List[str]] = None
    genre: Optional[str] = None
    type: Optional[str] = None
    bpm: Optional[float] = None
    version: Optional[str] = None
    charts: Optional[Chart] = None
    release_date: Optional[str] = None
    artist: Optional[str] = None

    diff: List[int] = []

    def __getattribute__(self, item):
        if item in {'genre', 'artist', 'release_date', 'bpm', 'version'}:
            if item == 'version':
                return self['basic_info']['from']
            return self['basic_info'][item]
        elif item in self:
            return self[item]
        return super().__getattribute__(item)


class MusicList(List[Music]):
    def by_id(self, music_id: str) -> Optional[Music]:
        for music in self:
            if music.id == music_id:
                return music
        return None

    def by_title(self, music_title: str) -> Optional[Music]:
        for music in self:
            if music.title == music_title:
                return music
        return None

    def random(self):
        return random.choice(self)

    def filter(self,
               *,
               level: Optional[Union[str, List[str]]] = ...,
               ds: Optional[Union[float, List[float], Tuple[float, float]]] = ...,
               title_search: Optional[str] = ...,
               genre: Optional[Union[str, List[str]]] = ...,
               artist: Optional[Union[str, List[str]]] = ...,
               charter: Optional[Union[str, List[str]]] = ...,
               bpm: Optional[Union[float, List[float], Tuple[float, float]]] = ...,
               type: Optional[Union[str, List[str]]] = ...,
               diff: List[int] = ...,
               is_new: bool = None,
               ):
        new_list = MusicList()
        for music in self:
            diff2 = diff
            music = deepcopy(music)
            ret, diff2 = cross(music.level, level, diff2)
            if not ret:
                continue
            ret, diff2 = cross(music.ds, ds, diff2)
            if not ret:
                continue
            if charter is not Ellipsis:
                ret, diff2 = cross([chart.charter.lower() for chart in music.charts], charter.lower(), diff2)
                if not ret:
                    continue
            if artist is not Ellipsis and not in_or_equal(music.artist.lower(), artist.lower()):
                continue
            if not in_or_equal(music.genre, genre):
                continue
            if not in_or_equal(music.type, type):
                continue
            if not in_or_equal(music.bpm, bpm):
                continue
            if is_new is not None and not music['basic_info']['is_new'] == is_new:
                continue
            if title_search is not Ellipsis and title_search.lower() not in music.title.lower():
                continue
            music.diff = diff2
            new_list.append(music)
        return new_list


# with open('src/static/data.json', encoding='utf-8') as f:
#    obj = json.load(f)
obj = requests.get('https://www.diving-fish.com/api/maimaidxprober/music_data').json()
total_list: MusicList = MusicList(obj)
for __i in range(len(total_list)):
    total_list[__i] = Music(total_list[__i])
    for __j in range(len(total_list[__i].charts)):
        total_list[__i].charts[__j] = Chart(total_list[__i].charts[__j])


# 处理数据，获得曲师和谱师列表
def get_artists_and_charters():
    artists = []
    charters = []
    for music in total_list:
        artist = music['basic_info']['artist']
        if artist not in artists:
            artists.append(artist)
        for i in range(2, len(music['charts'])):
            charter = music['charts'][i]['charter']
            if charter not in charters:
                charters.append(charter)
    return artists, charters


artist_list, charter_list = get_artists_and_charters()
chart_stats = requests.get('https://www.diving-fish.com/api/maimaidxprober/chart_stats').json()


async def update_chart_stats_and_count_list():
    global chart_stats
    global play_count_list
    global update_time
    chart_stats = requests.get('https://www.diving-fish.com/api/maimaidxprober/chart_stats').json()
    play_count_list = [[], [], [], [], [], []]
    for song_id in chart_stats:
        for i in range(5):
            if chart_stats[song_id][i].get('count'):
                play_count_list[i].append((song_id, chart_stats[song_id][i]['count']))
                play_count_list[5].append((song_id, chart_stats[song_id][i]['count'], i))
    for i in range(len(play_count_list)):
        play_count_list[i].sort(key=lambda elem: elem[1], reverse=True)
    update_time = datetime.now(SH).strftime('%Y/%m/%d %H:%M:%S')


# 处理数据，获得游玩次数排行列表
play_count_list = [[], [], [], [], [], []]

for song_id in chart_stats:
    for i in range(5):
        if chart_stats[song_id][i].get('count'):
            play_count_list[i].append((song_id, chart_stats[song_id][i]['count']))
            play_count_list[5].append((song_id, chart_stats[song_id][i]['count'], i))

for i in range(len(play_count_list)):
    play_count_list[i].sort(key=lambda elem: elem[1], reverse=True)

update_time = datetime.now(SH).strftime('%Y/%m/%d %H:%M:%S')
