import os
import json
import threading
from datetime import datetime
from flask import Flask, request

app = Flask(__name__)

BASE_DIR = os.path.expanduser("~/.openclaw/personal-health-data")
os.makedirs(BASE_DIR, exist_ok=True)

file_write_lock = threading.Lock()

@app.route('/health/today', methods=['POST'])
def receive_health():
    """接收 Health Auto Export 发来的 JSON 数据，追加写入当天日期命名的 .json 文件"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return "Invalid JSON", 400

    # 构建当前日期文件名（例如：2026-04-29.json）
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = os.path.join(BASE_DIR, f"{today}.json")

    # 统一解包 data 外层，确保最外层是 metrics
    normalized = data
    while isinstance(normalized, dict) and "data" in normalized and len(normalized) == 1:
        normalized = normalized["data"]
    if isinstance(normalized, dict) and "metrics" not in normalized:
        # 有明确类型名时直接借用，否则用 unknown
        data_payload = normalized.get("data", [])
        name = normalized.get("name", "unknown")
        units = normalized.get("units", "")
        normalized = {"metrics": [{"name": name, "units": units, "data": data_payload}]}

    # 覆盖写入文件
    try:
        with file_write_lock:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(normalized, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"写入文件失败: {e}")
        return "Server Error", 500

    now = datetime.now().strftime("%H:%M:%S.%f")

    # 控制台打印，便于实时观察
    print(f"[{now}] 收到数据并已写入 {filepath}  数据总长度为:{len(data)}")
    print(data)
    return "OK", 200

@app.route('/health/updateAll', methods=['POST'])
def update_all():
    """批量更新健康数据：按时间分组，覆盖对应日期文件"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return "Invalid JSON", 400

    # 先将原始输入数据保存到日志
    backup_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_log = os.path.join(BASE_DIR, f"backup_updateAll_{backup_timestamp}.log")
    with open(backup_log, "w", encoding="utf-8") as log_f:
        log_f.write(json.dumps(data, ensure_ascii=False, indent=2))
        log_f.write("\n")
    print(f"原始数据已保存到 {backup_log}")

    # 提取数据: 兼容 {"data": {"metrics": [...]}}, {"metrics": [...]}, [直接数组]
    metrics_meta = []

    # 解包可能的多层 data 包装
    while isinstance(data, dict) and "data" in data and len(data) == 1:
        data = data["data"]

    if not isinstance(data, dict):
        return "Invalid data format", 400

    metrics = data.get("metrics")
    if not metrics or not isinstance(metrics, list):
        metrics = [{"name": "step_count", "units": "count", "data": data.get("data", [])}]

    # 收集所有涉及的日期，按 (date, metric_name) 分组
    date_metric_map = {}  # {date_str: {metric_name: [records]}}
    metrics_meta = []     # [{name, units}]
    seen_metrics = set()

    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        name = metric.get("name", "unknown")
        units = metric.get("units", "")
        if name not in seen_metrics:
            metrics_meta.append({"name": name, "units": units})
            seen_metrics.add(name)
        metric_data = metric.get("data", [])
        if not isinstance(metric_data, list):
            continue
        for record in metric_data:
            date_str = extract_date(record)
            if date_str is None:
                continue
            if date_str not in date_metric_map:
                date_metric_map[date_str] = {}
            if name not in date_metric_map[date_str]:
                date_metric_map[date_str][name] = []
            date_metric_map[date_str][name].append(record)

    # 覆盖写入对应日期文件
    try:
        with file_write_lock:
            for date_str, metric_data in date_metric_map.items():
                filepath = os.path.join(BASE_DIR, f"{date_str}.json")
                output = {
                    "metrics": [
                        {
                            "name": m["name"],
                            "units": m["units"],
                            "data": metric_data.get(m["name"], [])
                        }
                        for m in metrics_meta
                    ]
                }
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"批量写入失败: {e}")
        return "Server Error", 500

    total = sum(len(v) for d in date_metric_map.values() for v in d.values())
    skipped = 0
    files_written = list(date_metric_map.keys())
    now = datetime.now().strftime("%H:%M:%S.%f")
    print(f"[{now}] 批量更新完成，写入 {len(files_written)} 个文件: {files_written}，"
          f"共 {total} 条记录")
    return {"status": "OK", "files": files_written, "total": total, "skipped": skipped}, 200


def extract_date(record):
    """从记录中提取日期字符串 YYYY-MM-DD"""
    if not isinstance(record, dict):
        return None
    for field in ("startDate", "endDate", "creationDate", "date"):
        val = record.get(field)
        if val and isinstance(val, str):
            return val[:10]  # "2026-04-29T12:00:00..." -> "2026-04-29"
    return None


@app.route('/health/test', methods=['POST'])
def receive_test():
    """测试接口：直接保存原始数据到 test.json"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return "Invalid JSON", 400

    filepath = os.path.join(BASE_DIR, "test.json")
    try:
        with file_write_lock:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"写入 test.json 失败: {e}", flush=True)
        return "Server Error", 500

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 测试数据已写入 {filepath}", flush=True)
    return "OK", 200


if __name__ == '__main__':
    # 监听所有网络接口，端口5000
    app.run(host='0.0.0.0', port=5000, debug=False)
