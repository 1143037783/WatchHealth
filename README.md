# WatchHealth

基于 Apple Watch 健康数据的个人健康查询技能，适用于 [OpenClaw](https://github.com/openclaw/openclaw) 平台。

## 功能

- 读取每日步数数据，计算总步数、活动分钟、最高单分钟步数
- 分析久坐行为，检测最长连续静止时段
- 支持多设备数据去重

## 数据结构

健康数据存放在 `~/.openclaw/personal-health-data/`，按日期存储为 JSON 文件，格式：

```json
{
  "metrics": [
    {
      "name": "step_count",
      "data": [
        {
          "date": "2026-05-05 08:30:00 +0800",
          "qty": 120,
          "source": "Apple Watch"
        }
      ]
    }
  ]
}
```

## 使用

在聊天中输入触发词即可查询，例如：

- "我今天走了多少步"
- "我的健康数据"
- "分析我的体检报告"

## 未来展望

- **扩展数据类型**：除步数外，接入心率、血氧、睡眠、卡路里等更多健康指标
- **多设备接入**：支持 Apple Watch、小米手环、华为手环等主流可穿戴设备的数据导入
- **多用户支持**：支持多个用户独立存储数据，实现数据隔离与权限管控

## 许可

MIT License
