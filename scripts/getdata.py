#!/usr/bin/env python3

import json
import os
from datetime import datetime
from collections import defaultdict

# 获取当前脚本所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__))
# 从脚本目录向上走 4 级到 /home/admin，再进入 .openclaw 数据目录
BASE_DIR = os.path.normpath(os.path.join(script_dir, "..", "..", "..", "..", ".openclaw", "personal-health-data"))

# ---------- 1. 读取今天的 JSON 文件 ----------
today = datetime.now().strftime("%Y-%m-%d")
filepath = os.path.join(BASE_DIR, f"{today}.json")

step_points = []   # [(datetime, qty, source)]

if os.path.exists(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    data = raw.get("data", raw)
    metrics = data.get("metrics", [])
    for metric in metrics:
        if metric.get("name") == "step_count":
            for point in metric.get("data", []):
                try:
                    dt = datetime.strptime(point["date"], "%Y-%m-%d %H:%M:%S %z")
                    qty = float(point["qty"])
                    source = point.get("source", "unknown")
                    step_points.append((dt, qty, source))
                except (ValueError, KeyError):
                    continue

if not step_points:
    result = {"总步数": 0, "活动分钟": 0, "错误": "今日无步数数据"}
    print(json.dumps(result, ensure_ascii=False))
    exit()

# 按时间排序
step_points.sort(key=lambda x: x[0])

# ---------- 3. 预处理：差分（假设 qty 是累计值） + 多设备去重 ----------
# 同一分钟取最大值（简单去重）
minute_map = defaultdict(float)
for dt, qty, src in step_points:
    minute_key = dt.strftime("%Y-%m-%d %H:%M")
    # 取该分钟所有设备中最大的 qty
    if qty > minute_map[minute_key]:
        minute_map[minute_key] = qty

# 转为排序的分钟序列
sorted_minutes = sorted(minute_map.keys())

# 直接累加每一分钟的步数，不再计算差值
minute_steps = [minute_map[m] for m in sorted_minutes]

# ---------- 4. 计算指标 ----------
total_steps = sum(minute_steps)  # 这里直接 sum
active_minutes = sum(1 for s in minute_steps if s > 0)
peak_minute = max(minute_steps) if minute_steps else 0

# 连续静止段（步数为0）
longest_sedentary = 0
for i in range(1, len(sorted_minutes)):
    # 将字符串时间转回 datetime 对象
    t1 = datetime.strptime(sorted_minutes[i-1], "%Y-%m-%d %H:%M")
    t2 = datetime.strptime(sorted_minutes[i], "%Y-%m-%d %H:%M")
    
    # 计算时间差（分钟）
    gap = (t2 - t1).total_seconds() / 60
    
    if gap > 1:
        # 如果中间空了超过1分钟，这些分钟就是久坐
        sedentary_time = gap - 1
        longest_sedentary = max(longest_sedentary, sedentary_time)

# 汇总指标
result = {
    "日期": today,
    "总步数": round(total_steps),
    "活动分钟": active_minutes,
    "最高单分钟步数": round(peak_minute),
    "最长久坐(分钟)": longest_sedentary
}

# 按你要求的格式输出
print(json.dumps(result, ensure_ascii=False))