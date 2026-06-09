import time

import select
from typing import List


# Python中的计时工具
# 高精度计时方法
def time_now():
    return time.time()


class TimeUtils:

    def __init__(self):
        self.current = None
        self.point_default_count = 0
        self.point_named_count = 0
        self.pointers = {}
        self.pointers_named = {}

    def cal(self, time_name:str):
        current_time = time_now()
        if time_name:
            if time_name not in self.pointers_named:
                self.pointers_named[time_name] = (self.point_named_count, current_time)
                self.point_named_count += 1
            else:
                raise ValueError("标签已存在，请更换标签")
        else:
            self.pointers[self.point_default_count] = (self.point_default_count, current_time)
            self.point_default_count += 1

    def cal_time(self, time_name_lst:List[str], use_name_list:bool=False, use_default_list:bool=True) -> str:
        if use_name_list and time_name_lst and len(time_name_lst) > 0:
            result_list = []
            for time_name in time_name_lst:
                time_tuple_of_name = self.pointers_named.get(time_name)
                # tuple数据按照tuple的第一个元素进行排序，从小到大
                result_list.append(time_tuple_of_name)
            # 得到排序后的结果
            result_sorted_list = sorted(result_list, key=lambda x:x[0])
            # 将排序后的结果按照区间计算

    def __cal_time_inner__(self, time1_tuple:tuple[str,float],time2_tuple:tuple[str, float] ):
        time1_name = time1_tuple[0]
        time2_name = time2_tuple[0]
        time1 = time1_tuple[1]
        time2 = time2_tuple[1]
        cost = abs(time1 - time2)
        if cost < 1:
            return f"{cost * 1000:.2f}ms"
        elif cost < 60:
            return f"{cost:.2f}s"
        elif cost < 3600:
            return f"{cost / 60:.2f}min"
        elif cost < 86400:
            return f"{cost / 3600:.2f}h"
        else:
            return f"{cost / 86400:.2f}day"

