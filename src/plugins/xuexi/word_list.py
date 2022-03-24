# from collections import defaultdict
#
# word_list = defaultdict(dict)
# f = open('src/static/jpns/n2wordlist.csv', 'r', encoding='utf-8')
# tmp = f.readlines()
# f.close()
# for t in tmp:
#     arr = t.strip().split('\t')
#     chn_list = arr[2].replace(" ", "").replace("，", " ").replace("；", " ").replace("．", " ").split()
#     new_dict = {'jap': arr[0], 'hira': arr[1], 'chn': chn_list}
#     if len(arr) == 4:
#         new_dict['type'] = arr[3]
#     else:
#         new_dict['type'] = ''
#     word_list[arr[0]] = new_dict
