import shelve
import time
import random
from nonebot.adapters import Bot


def hash(qq: int):
    days = int(time.strftime("%d", time.localtime(time.time()))) + 31 * int(
        time.strftime("%m", time.localtime(time.time())))
    random.seed(days * qq)
    return random.randint(114514, 1919810)


async def stat(bot: Bot, group_id: int, shelve_path: str, act_name: str, liang_ci: str = '次'):
    count_dict = shelve.open(shelve_path)
    if str(group_id) not in count_dict:
        count_dict.close()
        return f"你群还没有人{act_name}捏"
    group_stat = count_dict[str(group_id)]
    count_dict.close()
    sorted_list = sorted(list(group_stat.items()), key=lambda item: item[1], reverse=True)
    result = f"你群{act_name}情况："
    chinese_num_dict = {0: '一', 1: '二', 2: '三'}
    for i in range(min(3, len(sorted_list))):
        info = await bot.get_group_member_info(group_id=group_id, user_id=int(sorted_list[i][0]))
        name = info['card']
        if name == '':
            name = info['nickname']
        result += f"\n第{chinese_num_dict[i]}名：{name}({sorted_list[i][0]})，{sorted_list[i][1]}{liang_ci}"
    return result
