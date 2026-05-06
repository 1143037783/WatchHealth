#!/usr/bin/env python3

import json
import os
import math
from datetime import datetime, timedelta
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.normpath(os.path.join(script_dir, "..", "..", "..", "..", ".openclaw", "personal-health-data"))

today = datetime.now().strftime("%Y-%m-%d")
filepath = os.path.join(BASE_DIR, f"{today}.json")

if not os.path.exists(filepath):
    print(json.dumps({"日期": today, "错误": "今日无数据"}, ensure_ascii=False))
    exit()

with open(filepath, "r", encoding="utf-8") as f:
    raw = json.load(f)

# 兼容 {"data": {"metrics": [...]}} 和 {"metrics": [...]}
data_root = raw.get("data", raw)
metrics = data_root.get("metrics", [])

if not metrics:
    print(json.dumps({"日期": today, "错误": "无指标数据"}, ensure_ascii=False))
    exit()

# ---------- 解析所有指标 ----------
parsed = {}  # {metric_name: [(datetime, qty, source), ...]}

for metric in metrics:
    name = metric.get("name", "unknown")
    points = []
    for point in metric.get("data", []):
        try:
            dt = datetime.strptime(point["date"], "%Y-%m-%d %H:%M:%S %z")
            qty = float(point["qty"])
            source = point.get("source", "unknown")
            points.append((dt, qty, source))
        except (ValueError, KeyError):
            continue
    if points:
        points.sort(key=lambda x: x[0])
        parsed[name] = points


# ---------- 分析函数 ----------

def analyze_step_count(points, _name=None):
    """步数：分钟级去重，日汇总"""
    minute_map = defaultdict(float)
    for dt, qty, _ in points:
        minute_key = dt.strftime("%Y-%m-%d %H:%M")
        if qty > minute_map[minute_key]:
            minute_map[minute_key] = qty
    sorted_minutes = sorted(minute_map.keys())
    minute_values = [minute_map[m] for m in sorted_minutes]

    total = sum(minute_values)
    active_min = sum(1 for s in minute_values if s > 0)
    peak = max(minute_values) if minute_values else 0

    longest_sedentary = 0
    for i in range(1, len(sorted_minutes)):
        t1 = datetime.strptime(sorted_minutes[i - 1], "%Y-%m-%d %H:%M")
        t2 = datetime.strptime(sorted_minutes[i], "%Y-%m-%d %H:%M")
        gap = (t2 - t1).total_seconds() / 60
        if gap > 1:
            longest_sedentary = max(longest_sedentary, gap - 1)

    return {
        "总步数": round(total),
        "活动分钟": active_min,
        "最高单分钟步数": round(peak),
        "最长久坐(分钟)": round(longest_sedentary, 1),
    }


def analyze_active_energy(points, _name=None):
    """活动能量：取当日累计最终值"""
    max_qty = max(q for _, q, _ in points)
    return {"活动能量(kcal)": round(max_qty, 1)}


def analyze_heart_rate(points, metric_name):
    """心率类指标：最低、最高、平均"""
    label = LABELS.get(metric_name, metric_name)
    values = [q for _, q, _ in points]
    return {
        f"{label}_最低(bpm)": round(min(values), 1),
        f"{label}_最高(bpm)": round(max(values), 1),
        f"{label}_平均(bpm)": round(sum(values) / len(values), 1),
    }


def analyze_hrv(points, _name=None):
    """心率变异性：最低、最高、平均、SDNN"""
    values = [q for _, q, _ in points]
    avg = sum(values) / len(values)
    variance = sum((v - avg) ** 2 for v in values) / (len(values) - 1) if len(values) > 1 else 0
    sdnn = math.sqrt(variance)
    return {
        "心率变异性_最低(ms)": round(min(values), 1),
        "心率变异性_最高(ms)": round(max(values), 1),
        "心率变异性_平均(ms)": round(avg, 1),
        "心率变异性_SDNN(ms)": round(sdnn, 1),
    }


def analyze_vo2_max(points, _name=None):
    """最大摄氧量：取当日值"""
    latest = max(points, key=lambda x: x[0])
    return {"最大摄氧量(mL/kg/min)": round(latest[1], 1)}


def analyze_wrist_temperature(points, _name=None):
    """手腕温度：夜间均值 vs 7日基线"""
    # 只取 0:00-6:00 的夜间数据
    night_values = [q for dt, q, _ in points if dt.hour < 6]
    if not night_values:
        night_values = [q for _, q, _ in points]
    night_avg = sum(night_values) / len(night_values)

    # 计算过去7天基线
    baseline_avgs = []
    for i in range(1, 8):
        past_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        past_file = os.path.join(BASE_DIR, f"{past_date}.json")
        if not os.path.exists(past_file):
            continue
        try:
            with open(past_file, "r", encoding="utf-8") as f:
                past_raw = json.load(f)
            past_root = past_raw.get("data", past_raw)
            past_metrics = past_root.get("metrics", [])
            for m in past_metrics:
                if m.get("name") in ("wrist_temperature",):
                    vals = [float(p["qty"]) for p in m.get("data", [])
                            if p.get("qty") and datetime.strptime(p["date"], "%Y-%m-%d %H:%M:%S %z").hour < 6]
                    if vals:
                        baseline_avgs.append(sum(vals) / len(vals))
        except Exception:
            continue

    baseline = sum(baseline_avgs) / len(baseline_avgs) if baseline_avgs else None
    result = {"手腕温度_夜间均值(°C)": round(night_avg, 2)}
    if baseline is not None:
        result["手腕温度_基线(°C)"] = round(baseline, 2)
        result["手腕温度_偏离(°C)"] = round(night_avg - baseline, 2)
    return result


def analyze_respiratory_rate(points, _name=None):
    """呼吸频率：最低、最高、平均"""
    values = [q for _, q, _ in points]
    return {
        "呼吸频率_最低(次/分)": round(min(values), 1),
        "呼吸频率_最高(次/分)": round(max(values), 1),
        "呼吸频率_平均(次/分)": round(sum(values) / len(values), 1),
    }


def analyze_sleep(points, _name=None):
    """睡眠分析：总时长，各阶段分布"""
    if not points:
        return {}
    stages = defaultdict(float)
    for _, qty, _ in points:
        # qty 为睡眠阶段持续时间(分钟)，source 或 category 字段标识阶段
        pass

    # 睡眠数据通常结构不同 —— 按日期和阶段聚合
    # 此处保留接口，具体解析需根据 Health Auto Export 的睡眠数据格式适配
    return {"睡眠": "数据格式待适配"}


# ---------- 指标中文标签 ----------
LABELS = {
    "step_count": "步数",
    "active_energy": "活动能量",
    "resting_heart_rate": "静息心率",
    "heart_rate": "心率",
    "heart_rate_variability": "心率变异性",
    "vo2_max": "最大摄氧量",
    "wrist_temperature": "手腕温度",
    "respiratory_rate": "呼吸频率",
    "sleep_analysis": "睡眠分析",
}

# ---------- 指标到分析函数的映射 ----------
ANALYZERS = {
    "step_count": ("step_count", analyze_step_count),
    "active_energy": ("active_energy", analyze_active_energy),
    "resting_heart_rate": ("resting_heart_rate", analyze_heart_rate),
    "heart_rate": ("heart_rate", analyze_heart_rate),
    "heart_rate_variability": ("heart_rate_variability", analyze_hrv),
    "vo2_max": ("vo2_max", analyze_vo2_max),
    "wrist_temperature": ("wrist_temperature", analyze_wrist_temperature),
    "respiratory_rate": ("respiratory_rate", analyze_respiratory_rate),
    "sleep_analysis": ("sleep_analysis", analyze_sleep),
}


# ---------- 执行分析 ----------
result = {"日期": today}

for metric_name, points in parsed.items():
    entry = ANALYZERS.get(metric_name)
    if entry is None:
        continue
    _key, analyzer = entry
    try:
        result.update(analyzer(points, metric_name))
    except Exception as e:
        result[f"{metric_name}_分析错误"] = str(e)

print(json.dumps(result, ensure_ascii=False))
