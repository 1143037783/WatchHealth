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
        normalized = {"metrics": [{"name": "step_count", "units": "count", "data": normalized.get("data", [])}]}

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

    if isinstance(data, dict):
        metrics = data.get("metrics")
        if metrics and isinstance(metrics, list):
            all_records = []
            for metric in metrics:
                if isinstance(metric, dict):
                    meta = {k: metric[k] for k in ("name", "units") if k in metric}
                    metric_data = metric.get("data", [])
                    if isinstance(metric_data, list):
                        all_records.extend(metric_data)
                    meta["_count"] = len(metric_data)
                    metrics_meta.append(meta)
            records = all_records
        else:
            records = data.get("data")
            if records is None:
                records = data
    else:
        records = data
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        records = []

    # 按日期分组
    grouped = {}
    for record in records:
        date_str = extract_date(record)
        if date_str is None:
            continue
        grouped.setdefault(date_str, []).append(record)

    # 覆盖写入对应日期文件(保持 metrics 格式)
    if not metrics_meta:
        metrics_meta = [{"name": "step_count", "units": "count"}]
    try:
        with file_write_lock:
            for date_str, items in grouped.items():
                filepath = os.path.join(BASE_DIR, f"{date_str}.json")
                output = {
                    "metrics": [
                        {
                            "name": m["name"],
                            "units": m["units"],
                            "data": items
                        }
                        for m in metrics_meta
                    ]
                }
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"批量写入失败: {e}")
        return "Server Error", 500

    now = datetime.now().strftime("%H:%M:%S.%f")
    total = len(records)
    skipped = total - sum(len(v) for v in grouped.values())
    files_written = list(grouped.keys())
    print(f"[{now}] 批量更新完成，写入 {len(files_written)} 个文件: {files_written}，"
          f"共 {total} 条记录，跳过 {skipped} 条无日期记录")
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
    """测试接口：接收数据后直接保存到 test.json"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return "Invalid JSON", 400

    normalized = data
    while isinstance(normalized, dict) and "data" in normalized and len(normalized) == 1:
        normalized = normalized["data"]
    if isinstance(normalized, dict) and "metrics" not in normalized:
        normalized = {"metrics": [{"name": "step_count", "units": "count", "data": normalized.get("data", [])}]}

    filepath = os.path.join(BASE_DIR, "test.json")
    try:
        with file_write_lock:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(normalized, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"写入 test.json 失败: {e}")
        return "Server Error", 500

    now = datetime.now().strftime("%H:%M:%S.%f")
    print(f"[{now}] 测试数据已写入 {filepath}")
    return "OK", 200


if __name__ == '__main__':
    # 监听所有网络接口，端口5000
    app.run(host='0.0.0.0', port=5000, debug=False)
