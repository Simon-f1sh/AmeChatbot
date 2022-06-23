# Author: xyb, Diving_Fish
import asyncio
import os
import math
import re
import shelve
from random import shuffle
from typing import Optional, Dict, List, Tuple
from urllib.request import urlopen

import aiohttp
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from src.libraries.maimaidx_music import total_list, get_cover_len4_id
from src.libraries.image import text_to_image

scoreRank = 'D C B BB BBB A AA AAA S S+ SS SS+ SSS SSS+'.split(' ')
combo = ' FC FC+ AP AP+'.split(' ')
diffs = 'Basic Advanced Expert Master Re:Master'.split(' ')


class ChartInfo(object):
    def __init__(self, idNum: str, diff: int, tp: str, achievement: float, ra: int, comboId: int, scoreId: int,
                 title: str, ds: float, lv: str):
        self.idNum = idNum
        self.diff = diff
        self.tp = tp
        self.achievement = achievement
        self.ra = ra
        self.comboId = comboId
        self.scoreId = scoreId
        self.title = title
        self.ds = ds
        self.lv = lv

    def __str__(self):
        return '%-50s' % f'{self.title} [{self.tp}]' + f'{self.ds}\t{diffs[self.diff]}\t{self.ra}'

    def __eq__(self, other):
        return self.ra == other.ra

    def __lt__(self, other):
        return self.ra < other.ra

    @classmethod
    def from_json(cls, data):
        rate = ['d', 'c', 'b', 'bb', 'bbb', 'a', 'aa', 'aaa', 's', 'sp', 'ss', 'ssp', 'sss', 'sssp']
        ri = rate.index(data["rate"])
        fc = ['', 'fc', 'fcp', 'ap', 'app']
        fi = fc.index(data["fc"])
        return cls(
            idNum=total_list.by_title(data["title"]).id,
            title=data["title"],
            diff=data["level_index"],
            ra=data["ra"],
            ds=data["ds"],
            comboId=fi,
            scoreId=ri,
            lv=data["level"],
            achievement=data["achievements"],
            tp=data["type"]
        )


class BestList(object):

    def __init__(self, size: int):
        self.data = []
        self.size = size

    def push(self, elem: ChartInfo):
        if len(self.data) >= self.size and elem < self.data[-1]:
            return
        self.data.append(elem)
        self.data.sort()
        self.data.reverse()
        while (len(self.data) > self.size):
            del self.data[-1]

    def pop(self):
        del self.data[-1]

    def __str__(self):
        return '[\n\t' + ', \n\t'.join([str(ci) for ci in self.data]) + '\n]'

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        return self.data[index]


class DrawBest(object):

    def __init__(self, payload: Dict, sdBest: BestList, dxBest: BestList, userName: str, playerRating: int, musicRating: int):
        self.qq = payload.get("qq")
        self.sdBest = sdBest
        self.dxBest = dxBest
        self.userName = self._stringQ2B(userName)
        self.playerRating = playerRating
        self.musicRating = musicRating
        self.rankRating = self.playerRating - self.musicRating
        self.pic_dir = 'src/static/mai/pic/'
        self.cover_dir = 'src/static/mai/cover/'
        self.img = Image.open(self.pic_dir + 'UI_TTR_BG_Base_Plus.png').convert('RGBA')
        setting_dict = shelve.open('src/static/b40_setting.db')
        if not self.qq or self.qq not in setting_dict:
            setting_dict.close()
            self.avatar_index = "209501"
            self.plate_index = "200501_1"
        else:
            setting_stat = setting_dict[self.qq]
            setting_dict.close()
            if setting_stat.get("bg"):
                bg_size = self.img.size
                self.img = Image.open(self.pic_dir + f'bg/UI_Frame_{setting_stat["bg"]}.png').convert('RGBA')
                self.img = self.img.resize(bg_size).filter(ImageFilter.GaussianBlur(2))
            self.avatar_index = setting_stat["avatar"] if setting_stat.get("avatar") else None
            self.qq = None if self.avatar_index else self.qq
            self.plate_index = setting_stat["plate"] if setting_stat.get("plate") else "200501_1"
        self.ROWS_IMG = [2]
        for i in range(6):
            self.ROWS_IMG.append(116 + 96 * i)
        self.COLOUMS_IMG = []
        for i in range(6):
            self.COLOUMS_IMG.append(2 + 172 * i)
        for i in range(4):
            self.COLOUMS_IMG.append(888 + 172 * i)
        self.draw()

    def _Q2B(self, uchar):
        """单个字符 全角转半角"""
        inside_code = ord(uchar)
        if inside_code == 0x3000:
            inside_code = 0x0020
        else:
            inside_code -= 0xfee0
        if inside_code < 0x0020 or inside_code > 0x7e:  # 转完之后不是半角字符返回原来的字符
            return uchar
        return chr(inside_code)

    def _stringQ2B(self, ustring):
        """把字符串全角转半角"""
        return "".join([self._Q2B(uchar) for uchar in ustring])

    def _getCharWidth(self, o) -> int:
        widths = [
            (126, 1), (159, 0), (687, 1), (710, 0), (711, 1), (727, 0), (733, 1), (879, 0), (1154, 1), (1161, 0),
            (4347, 1), (4447, 2), (7467, 1), (7521, 0), (8369, 1), (8426, 0), (9000, 1), (9002, 2), (11021, 1),
            (12350, 2), (12351, 1), (12438, 2), (12442, 0), (19893, 2), (19967, 1), (55203, 2), (63743, 1),
            (64106, 2), (65039, 1), (65059, 0), (65131, 2), (65279, 1), (65376, 2), (65500, 1), (65510, 2),
            (120831, 1), (262141, 2), (1114109, 1),
        ]
        if o == 0xe or o == 0xf:
            return 0
        for num, wid in widths:
            if o <= num:
                return wid
        return 1

    def _coloumWidth(self, s: str):
        res = 0
        for ch in s:
            res += self._getCharWidth(ord(ch))
        return res

    def _changeColumnWidth(self, s: str, len: int) -> str:
        res = 0
        sList = []
        for ch in s:
            res += self._getCharWidth(ord(ch))
            if res <= len:
                sList.append(ch)
        return ''.join(sList)

    def _resizePic(self, img: Image.Image, time: float):
        return img.resize((int(img.size[0] * time), int(img.size[1] * time)))

    def _findRaPic(self) -> str:
        num = '10'
        if self.playerRating < 1000:
            num = '01'
        elif self.playerRating < 2000:
            num = '02'
        elif self.playerRating < 3000:
            num = '03'
        elif self.playerRating < 4000:
            num = '04'
        elif self.playerRating < 5000:
            num = '05'
        elif self.playerRating < 6000:
            num = '06'
        elif self.playerRating < 7000:
            num = '07'
        elif self.playerRating < 8000:
            num = '08'
        elif self.playerRating < 8500:
            num = '09'
        return f'UI_CMN_DXRating_S_{num}.png'

    def _drawRating(self, ratingBaseImg: Image.Image):
        COLOUMS_RATING = [86, 100, 115, 130, 145]
        theRa = self.playerRating
        i = 4
        while theRa:
            digit = theRa % 10
            theRa = theRa // 10
            digitImg = Image.open(self.pic_dir + f'UI_NUM_Drating_{digit}.png').convert('RGBA')
            digitImg = self._resizePic(digitImg, 0.6)
            ratingBaseImg.paste(digitImg, (COLOUMS_RATING[i] - 1, 11), mask=digitImg.split()[3])
            i = i - 1
        return ratingBaseImg

    def _drawBestList(self, img: Image.Image, sdBest: BestList, dxBest: BestList):
        itemW = 164
        itemH = 88
        Color = [(69, 193, 36), (255, 186, 1), (255, 90, 102), (134, 49, 200), (217, 197, 233)]
        levelTriagle = [(itemW, 0), (itemW - 27, 0), (itemW, 27)]
        rankPic = 'D C B BB BBB A AA AAA S Sp SS SSp SSS SSSp'.split(' ')
        comboPic = ' FC FCp AP APp'.split(' ')
        imgDraw = ImageDraw.Draw(img)
        titleFontName = 'src/static/adobe_simhei.otf'
        for num in range(0, len(sdBest)):
            i = num // 5
            j = num % 5
            chartInfo = sdBest[num]
            pngPath = self.cover_dir + f'{get_cover_len4_id(chartInfo.idNum)}.png'
            if not os.path.exists(pngPath):
                pngPath = self.cover_dir + '1000.png'
            temp = Image.open(pngPath).convert('RGB')
            temp = self._resizePic(temp, itemW / temp.size[0])
            temp = temp.crop((0, (temp.size[1] - itemH) / 2, itemW, (temp.size[1] + itemH) / 2))
            temp = temp.filter(ImageFilter.GaussianBlur(3))
            temp = temp.point(lambda p: p * 0.72)

            tempDraw = ImageDraw.Draw(temp)
            tempDraw.polygon(levelTriagle, Color[chartInfo.diff])
            font = ImageFont.truetype(titleFontName, 16, encoding='utf-8')
            title = chartInfo.title
            if self._coloumWidth(title) > 15:
                title = self._changeColumnWidth(title, 14) + '...'
            tempDraw.text((8, 8), title, 'white', font)
            font = ImageFont.truetype(titleFontName, 14, encoding='utf-8')

            tempDraw.text((7, 28), f'{"%.4f" % chartInfo.achievement}%', 'white', font)
            rankImg = Image.open(self.pic_dir + f'UI_GAM_Rank_{rankPic[chartInfo.scoreId]}.png').convert('RGBA')
            rankImg = self._resizePic(rankImg, 0.3)
            temp.paste(rankImg, (83, 29), rankImg.split()[3])
            if chartInfo.comboId:
                comboImg = Image.open(self.pic_dir + f'UI_MSS_MBase_Icon_{comboPic[chartInfo.comboId]}_S.png').convert(
                    'RGBA')
                comboImg = self._resizePic(comboImg, 0.45)
                temp.paste(comboImg, (119, 26), comboImg.split()[3])
            font = ImageFont.truetype('src/static/adobe_simhei.otf', 12, encoding='utf-8')
            tempDraw.text((8, 44), f'Base: {chartInfo.ds} -> {chartInfo.ra}', 'white', font)
            font = ImageFont.truetype('src/static/adobe_simhei.otf', 18, encoding='utf-8')
            tempDraw.text((8, 60), f'#{num + 1}', 'white', font)

            recBase = Image.new('RGBA', (itemW, itemH), 'black')
            recBase = recBase.point(lambda p: p * 0.8)
            img.paste(recBase, (self.COLOUMS_IMG[j] + 5, self.ROWS_IMG[i + 1] + 5))
            img.paste(temp, (self.COLOUMS_IMG[j] + 4, self.ROWS_IMG[i + 1] + 4))
        for num in range(len(sdBest), sdBest.size):
            i = num // 5
            j = num % 5
            temp = Image.open(self.cover_dir + f'1000.png').convert('RGB')
            temp = self._resizePic(temp, itemW / temp.size[0])
            temp = temp.crop((0, (temp.size[1] - itemH) / 2, itemW, (temp.size[1] + itemH) / 2))
            temp = temp.filter(ImageFilter.GaussianBlur(1))
            img.paste(temp, (self.COLOUMS_IMG[j] + 4, self.ROWS_IMG[i + 1] + 4))
        for num in range(0, len(dxBest)):
            i = num // 3
            j = num % 3
            chartInfo = dxBest[num]
            pngPath = self.cover_dir + f'{get_cover_len4_id(chartInfo.idNum)}.png'
            if not os.path.exists(pngPath):
                pngPath = self.cover_dir + f'{get_cover_len4_id(chartInfo.idNum)}.png'
            if not os.path.exists(pngPath):
                pngPath = self.cover_dir + '1000.png'
            temp = Image.open(pngPath).convert('RGB')
            temp = self._resizePic(temp, itemW / temp.size[0])
            temp = temp.crop((0, (temp.size[1] - itemH) / 2, itemW, (temp.size[1] + itemH) / 2))
            temp = temp.filter(ImageFilter.GaussianBlur(3))
            temp = temp.point(lambda p: p * 0.72)

            tempDraw = ImageDraw.Draw(temp)
            tempDraw.polygon(levelTriagle, Color[chartInfo.diff])
            font = ImageFont.truetype(titleFontName, 16, encoding='utf-8')
            title = chartInfo.title
            if self._coloumWidth(title) > 15:
                title = self._changeColumnWidth(title, 14) + '...'
            tempDraw.text((8, 8), title, 'white', font)
            font = ImageFont.truetype(titleFontName, 14, encoding='utf-8')

            tempDraw.text((7, 28), f'{"%.4f" % chartInfo.achievement}%', 'white', font)
            rankImg = Image.open(self.pic_dir + f'UI_GAM_Rank_{rankPic[chartInfo.scoreId]}.png').convert('RGBA')
            rankImg = self._resizePic(rankImg, 0.3)
            temp.paste(rankImg, (83, 29), rankImg.split()[3])
            if chartInfo.comboId:
                comboImg = Image.open(self.pic_dir + f'UI_MSS_MBase_Icon_{comboPic[chartInfo.comboId]}_S.png').convert(
                    'RGBA')
                comboImg = self._resizePic(comboImg, 0.45)
                temp.paste(comboImg, (119, 26), comboImg.split()[3])
            font = ImageFont.truetype('src/static/adobe_simhei.otf', 12, encoding='utf-8')
            tempDraw.text((8, 44), f'Base: {chartInfo.ds} -> {chartInfo.ra}', 'white', font)
            font = ImageFont.truetype('src/static/adobe_simhei.otf', 18, encoding='utf-8')
            tempDraw.text((8, 60), f'#{num + 1}', 'white', font)

            recBase = Image.new('RGBA', (itemW, itemH), 'black')
            recBase = recBase.point(lambda p: p * 0.8)
            img.paste(recBase, (self.COLOUMS_IMG[j + 6] + 5, self.ROWS_IMG[i + 1] + 5))
            img.paste(temp, (self.COLOUMS_IMG[j + 6] + 4, self.ROWS_IMG[i + 1] + 4))
        for num in range(len(dxBest), dxBest.size):
            i = num // 3
            j = num % 3
            temp = Image.open(self.cover_dir + f'1000.png').convert('RGB')
            temp = self._resizePic(temp, itemW / temp.size[0])
            temp = temp.crop((0, (temp.size[1] - itemH) / 2, itemW, (temp.size[1] + itemH) / 2))
            temp = temp.filter(ImageFilter.GaussianBlur(1))
            img.paste(temp, (self.COLOUMS_IMG[j + 6] + 4, self.ROWS_IMG[i + 1] + 4))

    def draw(self):
        plate = Image.open(self.pic_dir + f'plate/UI_Plate_{self.plate_index}.png').convert('RGBA')
        plate = self._resizePic(plate, 0.90)
        self.img.paste(plate, (6, 8), mask=plate.split()[3])

        if self.qq:
            response = requests.get(f"https://ssl.ptlogin2.qq.com/getface?imgtype=4&uin={self.qq}")
            regex = r'pt.setHeader\({"' + self.qq + r'":"(.+)"}\)'
            avatar_ori = Image.open(urlopen(re.match(regex, response.text).group(1))).convert('RGBA').resize((140, 140))
            avatar_frame = Image.open(self.pic_dir + 'avatar_frame.png').convert('RGBA')
            avatar_ori_w, avatar_ori_h = avatar_ori.size
            avatar = Image.new('RGB', (avatar_ori_w + 20, avatar_ori_h + 20), (255, 255, 255))
            avatar.paste(avatar_ori, (10, 10))
            mask = Image.new("L", avatar.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((8, 8, avatar_ori_w + 11, avatar_ori_h + 11), fill=255)
            avatar_frame = self._resizePic(avatar_frame, avatar.size[0] / avatar_frame.size[0])
            avatar = Image.composite(avatar, avatar_frame, mask)
            avatar = self._resizePic(avatar, 0.55)
            self.img.paste(avatar, (15, 15), mask=avatar.split()[3])
        else:
            avatar = Image.open(self.pic_dir + f'avatar/UI_Icon_{self.avatar_index}.png').convert('RGBA')
            avatar = avatar.resize((89, 89))
            self.img.paste(avatar, (15, 15), mask=avatar.split()[3])
        # splashLogo = Image.open(self.pic_dir + 'UI_CMN_TabTitle_MaimaiTitle_Ver214.png').convert('RGBA')

        ratingBaseImg = Image.open(self.pic_dir + self._findRaPic()).convert('RGBA')
        ratingBaseImg = self._drawRating(ratingBaseImg)
        ratingBaseImg = self._resizePic(ratingBaseImg, 0.855)
        self.img.paste(ratingBaseImg, (108, 11), mask=ratingBaseImg.split()[3])

        namePlateImg = Image.open(self.pic_dir + 'UI_TST_PlateMask.png').convert('RGBA')
        namePlateImg = namePlateImg.resize((280, 40))
        namePlateDraw = ImageDraw.Draw(namePlateImg)
        font1 = ImageFont.truetype('src/static/msyh.ttc', 28, encoding='unic')
        namePlateDraw.text((12, 1), ' '.join(list(self.userName)), 'black', font1)
        nameDxImg = Image.open(self.pic_dir + 'UI_CMN_Name_DX.png').convert('RGBA')
        nameDxImg = self._resizePic(nameDxImg, 0.9)
        namePlateImg.paste(nameDxImg, (230, 4), mask=nameDxImg.split()[3])
        namePlateImg = self._resizePic(namePlateImg, 0.84)
        self.img.paste(namePlateImg, (110, 48), mask=namePlateImg.split()[3])

        shougouImg = Image.open(self.pic_dir + 'UI_CMN_Shougou_Rainbow.png').convert('RGBA')
        shougouDraw = ImageDraw.Draw(shougouImg)
        font2 = ImageFont.truetype('src/static/adobe_simhei.otf', 14, encoding='utf-8')
        playCountInfo = f'底分: {self.musicRating} + 段位分: {self.rankRating}'
        shougouImgW, shougouImgH = shougouImg.size
        playCountInfoW, playCountInfoH = shougouDraw.textsize(playCountInfo, font2)
        textPos = ((shougouImgW - playCountInfoW - font2.getoffset(playCountInfo)[0]) / 2, 8)
        shougouDraw.text((textPos[0] - 1, textPos[1]), playCountInfo, 'black', font2)
        shougouDraw.text((textPos[0] + 1, textPos[1]), playCountInfo, 'black', font2)
        shougouDraw.text((textPos[0], textPos[1] - 1), playCountInfo, 'black', font2)
        shougouDraw.text((textPos[0], textPos[1] + 1), playCountInfo, 'black', font2)
        shougouDraw.text((textPos[0] - 1, textPos[1] - 1), playCountInfo, 'black', font2)
        shougouDraw.text((textPos[0] + 1, textPos[1] - 1), playCountInfo, 'black', font2)
        shougouDraw.text((textPos[0] - 1, textPos[1] + 1), playCountInfo, 'black', font2)
        shougouDraw.text((textPos[0] + 1, textPos[1] + 1), playCountInfo, 'black', font2)
        shougouDraw.text(textPos, playCountInfo, 'white', font2)
        shougouImg = self._resizePic(shougouImg, 0.88)
        self.img.paste(shougouImg, (107, 81), mask=shougouImg.split()[3])

        self._drawBestList(self.img, self.sdBest, self.dxBest)

        authorBoardImg = Image.open(self.pic_dir + 'UI_CMN_MiniDialog_01.png').convert('RGBA')
        authorBoardImg = self._resizePic(authorBoardImg, 0.35)
        authorBoardDraw = ImageDraw.Draw(authorBoardImg)
        font_author = ImageFont.truetype('src/static/adobe_simhei.otf', 12, encoding='utf-8')
        authorBoardDraw.text((42, 30), '      Credit to\nXybBot & Chiyuki\n   Generated By\n        Ame bot', 'black', font_author)
        self.img.paste(authorBoardImg, (1220, 6), mask=authorBoardImg.split()[3])

        dxImg = Image.open(self.pic_dir + 'UI_RSL_MBase_Parts_01.png').convert('RGBA')
        self.img.paste(dxImg, (890, 85), mask=dxImg.split()[3])
        sdImg = Image.open(self.pic_dir + 'UI_RSL_MBase_Parts_02.png').convert('RGBA')
        self.img.paste(sdImg, (775, 85), mask=sdImg.split()[3])

        # self.img.show()

    def getDir(self):
        return self.img


def compute_ra(ds: float, achievement: float) -> int:
    baseRa = 14.0
    if achievement < 50:
        baseRa = 1.0
    if 50 <= achievement < 60:
        baseRa = 5.0
    elif achievement < 70:
        baseRa = 6.0
    elif achievement < 75:
        baseRa = 7.0
    elif achievement < 80:
        baseRa = 7.5
    elif achievement < 90:
        baseRa = 8.5
    elif achievement < 94:
        baseRa = 9.5
    elif achievement < 97:
        baseRa = 10.5
    elif achievement < 98:
        baseRa = 12.5
    elif achievement < 99:
        baseRa = 12.7
    elif achievement < 99.5:
        baseRa = 13.0
    elif achievement < 100:
        baseRa = 13.2
    elif achievement < 100.5:
        baseRa = 13.5

    return math.floor(ds * (min(100.5, achievement) / 100) * baseRa)


def truncate(number, digits) -> float:
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper


def compute_ds(ra: int, achievement: float) -> float:
    baseRa = 14.0
    if achievement < 50:
        baseRa = 1.0
    if 50 <= achievement < 60:
        baseRa = 5.0
    elif achievement < 70:
        baseRa = 6.0
    elif achievement < 75:
        baseRa = 7.0
    elif achievement < 80:
        baseRa = 7.5
    elif achievement < 90:
        baseRa = 8.5
    elif achievement < 94:
        baseRa = 9.5
    elif achievement < 97:
        baseRa = 10.5
    elif achievement < 98:
        baseRa = 12.5
    elif achievement < 99:
        baseRa = 12.7
    elif achievement < 99.5:
        baseRa = 13.0
    elif achievement < 100:
        baseRa = 13.2
    elif achievement < 100.5:
        baseRa = 13.5

    ds = math.ceil(ra / (min(100.5, achievement) / 100) / baseRa * 10) / 10

    return ds


async def generate(payload: Dict) -> Tuple[Optional[Image.Image], bool]:
    async with aiohttp.request("POST", "https://www.diving-fish.com/api/maimaidxprober/query/player",
                               json=payload) as resp:
        if resp.status == 400:
            return None, 400
        if resp.status == 403:
            return None, 403
        sd_best = BestList(25)
        dx_best = BestList(15)
        obj = await resp.json()
        dx: List[Dict] = obj["charts"]["dx"]
        sd: List[Dict] = obj["charts"]["sd"]
        for c in sd:
            sd_best.push(ChartInfo.from_json(c))
        for c in dx:
            dx_best.push(ChartInfo.from_json(c))
        pic = DrawBest(payload, sd_best, dx_best, obj["nickname"], obj["rating"] + obj["additional_rating"],
                       obj["rating"]).getDir()
        return pic, 0


def random_musics(sample_list: List, b40_list: List, lowest_ra: int, num: int, prev_list: List = None) -> List:
    ret_list = []
    if prev_list:
        ret_list.extend(prev_list)
    for music in sample_list:
        # print(music)
        found = next((item for item in b40_list if
                      item['title'] == music.title and item['ds'] == music.ds[music.diff[0]]), None)
        if not found:
            music['100'] = compute_ra(music.ds[music.diff[0]], 100.0) - lowest_ra
            music['100.5'] = compute_ra(music.ds[music.diff[0]], 100.5) - lowest_ra
        else:
            if found['achievements'] < 100.5:
                if found['achievements'] < 100:
                    music['100'] = compute_ra(music.ds[music.diff[0]], 100.0) - found['ra']
                else:
                    music['100'] = 0.0
                music['100.5'] = compute_ra(music.ds[music.diff[0]], 100.5) - found['ra']
            else:
                continue
        if music['100.5'] == 0:
            continue
        ret_list.append(music)
        if len(ret_list) >= num:
            break
    return ret_list


async def analyze(payload: Dict, num: int = 3) -> Tuple[Optional[Image.Image], bool]:
    async with aiohttp.request("POST", "https://www.diving-fish.com/api/maimaidxprober/query/player",
                               json=payload) as resp:
        if resp.status == 400:
            return None, 400
        if resp.status == 403:
            return None, 403
        sd_best = BestList(25)
        dx_best = BestList(15)
        obj = await resp.json()
        # print(obj)
        dx: List[Dict] = obj["charts"]["dx"]
        sd: List[Dict] = obj["charts"]["sd"]
        dx_ra = 0
        sd_ra = 0
        for c in sd:
            sd_best.push(ChartInfo.from_json(c))
            sd_ra += c["ra"]
        for c in dx:
            dx_best.push(ChartInfo.from_json(c))
            dx_ra += c["ra"]

        sd_length = len(sd_best)
        dx_length = len(dx_best)
        if sd_length == 0 and dx_length == 0:
            return None, -1
        diff_list = ["Bas", "Adv", "Exp", "Mas", "ReM"]

        analysis_text = f"""{obj["nickname"]}的底分分析如下"""
        if sd_length > 0:
            sd_lowest_ra = sd_best[sd_length - 1].ra
            sd_upper_ds = round(compute_ds(sd_lowest_ra, 99.5) + 0.1, 1)
            sd_lower_ds = round(compute_ds(sd_lowest_ra, 100.5) + 0.1, 1)
            sd_sample_list = total_list.filter(ds=(sd_lower_ds, sd_upper_ds), is_new=False)
            shuffle(sd_sample_list)
            sd_chosen_list = random_musics(sd_sample_list, sd, sd_lowest_ra if sd_length == 25 else 0, num)
            achievement = 99.5
            while len(sd_chosen_list) < num and round(sd_upper_ds + 0.1, 1) <= 15.0 and achievement > 0:
                achievement = round(achievement - 1.0)
                sd_lower_ds = round(sd_upper_ds + 0.1, 1)
                sd_upper_ds = round(compute_ds(sd_lowest_ra, achievement) + 0.1, 1)
                sd_sample_list = total_list.filter(ds=(sd_lower_ds, sd_upper_ds), is_new=False)
                shuffle(sd_sample_list)
                print(sd_lower_ds, sd_upper_ds)
                sd_chosen_list = random_musics(sd_sample_list, sd, sd_lowest_ra if sd_length == 25 else 0, num, sd_chosen_list)

            sd_h_sssp = compute_ds(sd_best[0].ra, 100.5)
            sd_h_sss = compute_ds(sd_best[0].ra, 100)
            sd_h_ss = compute_ds(sd_best[0].ra, 99)
            sd_l_sssp = compute_ds(sd_lowest_ra, 100.5)
            sd_l_sss = compute_ds(sd_lowest_ra, 100)
            sd_l_ss = compute_ds(sd_lowest_ra, 99)

            analysis_text += f"""
--------------------------
你的b25分值为{sd_ra}
最高为{sd_best[0].ra}，约为{sd_h_sssp}的100.5% {(str(sd_h_sss) + "的100%") if sd_h_sss <= 15.0 else ""} {(str(sd_h_ss) + "的99%") if sd_h_ss <= 15.0 else ""}
最低为{sd_lowest_ra}，约为{sd_l_sssp}的100.5% {(str(sd_l_sss) + "的100%") if sd_l_sss <= 15.0 else ""} {(str(sd_l_ss) + "的99%") if sd_l_ss <= 15.0 else ""}
随机提分金曲："""

            for music in sd_chosen_list:
                analysis_text += f"""
{music.id}. {music.title} ({diff_list[music.diff[0]]}) {music.ds[music.diff[0]]}
目标： {("100% Rating+" + str(music['100']) + " / ") if music['100'] > 0 else ""}100.5% Rating+{music['100.5']}"""

        if dx_length > 0:
            dx_lowest_ra = dx_best[dx_length - 1].ra
            dx_upper_ds = round(compute_ds(dx_lowest_ra, 99.5) + 0.1, 1)
            dx_lower_ds = round(compute_ds(dx_lowest_ra, 100.5) + 0.1, 1)
            dx_sample_list = total_list.filter(ds=(dx_lower_ds, dx_upper_ds), is_new=True)
            shuffle(dx_sample_list)
            dx_chosen_list = random_musics(dx_sample_list, dx, dx_lowest_ra if dx_length == 15 else 0, num)
            achievement = 99.5
            while len(dx_chosen_list) < num and round(dx_upper_ds + 0.1, 1) <= 15.0 and achievement > 0:
                achievement = round(achievement - 1.0)
                dx_lower_ds = round(dx_upper_ds + 0.1, 1)
                dx_upper_ds = round(compute_ds(dx_lowest_ra, achievement) + 0.1, 1)
                dx_sample_list = total_list.filter(ds=(dx_lower_ds, dx_upper_ds), is_new=True)
                shuffle(dx_sample_list)
                print(dx_lower_ds, dx_upper_ds)
                dx_chosen_list = random_musics(dx_sample_list, dx, dx_lowest_ra if dx_length == 15 else 0, num, dx_chosen_list)

            dx_h_sssp = compute_ds(dx_best[0].ra, 100.5)
            dx_h_sss = compute_ds(dx_best[0].ra, 100)
            dx_h_ss = compute_ds(dx_best[0].ra, 99)
            dx_l_sssp = compute_ds(dx_lowest_ra, 100.5)
            dx_l_sss = compute_ds(dx_lowest_ra, 100)
            dx_l_ss = compute_ds(dx_lowest_ra, 99)

            analysis_text += f"""
--------------------------
你的b15分值为{dx_ra}
最高为{dx_best[0].ra}，约为{dx_h_sssp}的100.5% {(str(dx_h_sss) + "的100%") if dx_h_sss <= 15.0 else ""} {(str(dx_h_ss) + "的99%") if dx_h_ss <= 15.0 else ""}
最低为{dx_lowest_ra}，约为{dx_l_sssp}的100.5% {(str(dx_l_sss) + "的100%") if dx_l_sss <= 15.0 else ""} {(str(dx_l_ss) + "的99%") if dx_l_ss <= 15.0 else ""}
随机提分金曲："""

            for music in dx_chosen_list:
                analysis_text += f"""
{music.id}. {music.title} ({diff_list[music.diff[0]]}) {music.ds[music.diff[0]]}
目标： {("100% Rating+" + str(music['100']) + " / ") if music['100'] > 0 else ""}100.5% Rating+{music['100.5']}"""

        pic = text_to_image(analysis_text)
        # DrawBest(sd_best, dx_best, obj["nickname"], obj["rating"] + obj["additional_rating"], obj["rating"]).getDir()
        return pic, 0
