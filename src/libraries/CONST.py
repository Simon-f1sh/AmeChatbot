# from os import path

CQMsg = {'face': '[CQ:face,id={}]',
         'record': '[CQ:record,file={}]',
         'image': '[CQ:image,file={}]',
         'poke': '[CQ:poke,qq={}]',
         'at': '[CQ:at,qq={}]',
         'reply': '[CQ:reply,id={}]',
         'tts': '[CQ:tts,text={}]'
         }

# MAINDIR=path.realpath('/').replace('\\', '/')
# IMAGE_LOCALDIR=MAINDIR+'/yiban/images/'
# RESOURCE_LOCALDIR=MAINDIR+'/yiban/resources/'
# TEMP_LOCALDIR=MAINDIR+'/yiban/temp/'
#
# LOCALDIR={'image':MAINDIR+'/yiban/images/',
#           'resource':MAINDIR+'/yiban/resources/',
#           'temp':MAINDIR+'/yiban/temp/'
#           }

static_folder = "src/static/"
mai_tmp_folder = "src/static/mai/tmp/"
record_folder = "src/static/record/"
poke_img_folder = "src/static/mai/poke/img/"
audio_folder = "src/static/audio/"
food_folder = "src/static/image/food/"
help_folder = "src/static/help/"
general_sticker_folder = "src/static/sticker/general/"
sticker_folder_dict = dict.fromkeys(["ongeki"], ["音击表情包", "src/static/sticker/ongeki/"])
sticker_folder_dict.update(dict.fromkeys(["iromido", "irodorimidori"], ["彩绿表情包", "src/static/sticker/iromido/"]))
sticker_folder_dict.update(dict.fromkeys(["djw", "caibi"], ["蹛檟痏表情包", "src/static/sticker/djw/"]))
# 将多对一dict反转成一对多以方便展示可用标签和描述
sticker_hashtag_dict = {}
for k, v in sticker_folder_dict.items():
    sticker_hashtag_dict[v[0]] = sticker_hashtag_dict.get(v[0], "") + f"#{k} "
