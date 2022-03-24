from os import path

CQMsg={'face':'[CQ:face,id={}]',
       'record':'[CQ:record,file={}]',
       'image':'[CQ:image,file={}]',
       'poke':'[CQ:poke,qq={}]',
       'at':'[CQ:at,qq={}]',
       'reply':'[CQ:reply,id={}]',
       'tts':'[CQ:tts,text={}]'
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
tmp_folder = "src/static/tmp/"
record_folder = "src/static/record/"
poke_img_folder = "src/static/mai/poke/img/"
audio_folder = "src/static/audio/"
general_sticker_folder = "src/static/sticker/general/"
ongeki_sticker_folder = "src/static/sticker/ongeki/"
food_folder = "src/static/image/food/"
help_folder = "src/static/help/"

