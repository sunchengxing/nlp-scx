import time
from typing import List


def time_now():
    return time.time()


class TimeUtils:

    def __init__(self):
        self.point_default_count = 0
        self.point_named_count = 0

        # {index: (index, timestamp)}
        self.pointers = {}

        # {name: (index, timestamp)}
        self.pointers_named = {}

    def cal(self, time_name: str = ""):
        current_time = time_now()

        if time_name:
            if time_name in self.pointers_named:
                raise ValueError(f"标签 [{time_name}] 已存在")

            self.pointers_named[time_name] = (
                self.point_named_count,
                current_time
            )

            self.point_named_count += 1

        else:
            self.pointers[self.point_default_count] = (
                self.point_default_count,
                current_time
            )

            self.point_default_count += 1

    def cal_time(
            self,
            time_name_lst: List[str],
            use_name_list: bool = False
    ) -> str:

        if not use_name_list:
            return ""

        result_list = []

        for time_name in time_name_lst:

            time_info = self.pointers_named.get(time_name)

            if time_info is None:
                raise ValueError(f"未找到标签 [{time_name}]")

            result_list.append(
                (
                    time_name,      # 名称
                    time_info[0],   # index
                    time_info[1]    # timestamp
                )
            )

        # 按记录顺序排序
        result_list.sort(key=lambda x: x[1])

        result = []

        for i in range(1, len(result_list)):
            result.append(
                self.__cal_time_inner__(
                    result_list[i - 1],
                    result_list[i]
                )
            )

        return "\n".join(result)

    def __cal_time_inner__(
            self,
            time1_tuple: tuple[str, int, float],
            time2_tuple: tuple[str, int, float]
    ) -> str:

        time1_name = time1_tuple[0]
        time2_name = time2_tuple[0]

        time1 = time1_tuple[2]
        time2 = time2_tuple[2]

        cost = abs(time2 - time1)

        if cost < 1:
            cost_str = f"{cost * 1000:.2f}ms"
        elif cost < 60:
            cost_str = f"{cost:.2f}s"
        elif cost < 3600:
            cost_str = f"{cost / 60:.2f}min"
        elif cost < 86400:
            cost_str = f"{cost / 3600:.2f}h"
        else:
            cost_str = f"{cost / 86400:.2f}day"

        return f"{time1_name} -> {time2_name}: {cost_str}"