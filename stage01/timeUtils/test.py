import time

from stage01.timeUtils.time_utils_class import TimeUtils

t = TimeUtils()

t.cal("开始")
time.sleep(0.1)

t.cal("加载")
time.sleep(2)

t.cal("结束")

print(
    t.cal_time(
        ["开始", "加载", "结束"],
        use_name_list=True
    )
)