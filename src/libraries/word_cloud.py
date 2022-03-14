from io import BytesIO

import wordcloud
from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator
import os
import glob
import jieba.posseg as pseg
import numpy as np
from PIL import Image


def read_file(filename):
    content = ""
    with open(filename, "r", encoding="UTF-8") as f:
        line = f.readline()
        while line:
            if "http" not in line:
                content += line
            line = f.readline()
    return content


def read_stop_words_file(filename):
    with open(filename, "r", encoding="UTF-8") as f:
        stop_word = f.readlines()
    return [word.replace("\n", "") for word in stop_word]


def fetch_records(folder: str, start_date: str, end_date: str = None):
    all_txt_files = glob.glob(f"{folder}*.txt")
    if end_date:
        txt_files = list(filter(lambda x: start_date <= x[-12:-4] <= end_date, all_txt_files))
    else:
        txt_files = list(filter(lambda x: start_date == x[-12:-4], all_txt_files))
    print(start_date, end_date, txt_files)
    if len(txt_files) == 0:
        return None
    return txt_files


def wordcloud_generate(txt_files: list):
    background = np.array(Image.open("src/static/wordcloud/background/xinao2022.jpg"))
    content_strings = "".join(list(map(read_file, txt_files)))
    flagged_words = pseg.cut(content_strings)
    wordlist = []
    for word, flag in flagged_words:
        if flag not in [] and (flag != "d" or len(word) != 1):
            wordlist.append(word)
    space_list = " ".join(wordlist).replace("\n", "")
    stop_words_path = "src/static/wordcloud/stopwords/"
    stop_words_files = ["cn_stopwords.txt", "hit_stopwords.txt", "baidu_stopwords.txt", "scu_stopwords.txt",
                        "maimai_stopwords.txt"]
    stop_words = []
    for file in stop_words_files:
        stop_words += read_stop_words_file(os.path.join(stop_words_path, file))
    stop_words = set(stop_words)

    wc = WordCloud(width=1400, height=2200,
                   background_color='white',
                   mode='RGB',
                   mask=background,  # 添加蒙版，生成指定形状的词云，并且词云图的颜色可从蒙版里提取
                   max_words=500,
                   stopwords=set.union(STOPWORDS, stop_words),  # 内置的屏蔽词,并添加自己设置的词语
                   font_path="src/static/wordcloud/fonts/chinese.stzhongs.ttf",
                   max_font_size=150,
                   relative_scaling=0.6,  # 设置字体大小与词频的关联程度为0.4
                   random_state=50,
                   scale=2
                   ).generate(space_list)

    image_color = ImageColorGenerator(background)  # 设置生成词云的颜色，如去掉这两行则字体为默认颜色
    return wc.recolor(color_func=image_color)
