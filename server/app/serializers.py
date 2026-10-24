"""统一的对外序列化工具：所有时间以 UTC、ISO8601 且带 'Z' 输出，避免前端按本地时区误解析。"""
from datetime import datetime


def iso(value: datetime | None):
    if value is None:
        return None
    text = value.isoformat()
    return text if value.tzinfo else text + 'Z'
