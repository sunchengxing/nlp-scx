from typing import List


def cal_time(
        self,
        time_name_lst: List[str],
        use_name_list: bool = False,
        use_default_list: bool = True
) -> str:

    if use_name_list and time_name_lst:

        result_list = []

        for time_name in time_name_lst:
            time_tuple = self.pointers_named.get(time_name)

            if time_tuple is None:
                continue

            # (name, index, timestamp)
            result_list.append(
                (time_name, time_tuple[0], time_tuple[1])
            )

        # 按记录顺序排序
        result_sorted_list = sorted(result_list, key=lambda x: x[1])

        result = []

        for i in range(1, len(result_sorted_list)):
            prev = result_sorted_list[i - 1]
            curr = result_sorted_list[i]

            result.append(
                self.__cal_time_inner__(prev, curr)
            )

        return "\n".join(result)

    return ""


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