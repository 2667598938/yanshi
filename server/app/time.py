from datetime import datetime, timezone


def utcnow():
    """全项目统一的 UTC 时间（naive UTC）。

    MySQL / SQLite 的 DATETIME 都不保留时区，因此 Python 内部与数据库统一用
    naive UTC，避免同一字段在「刚写入对象」和「从库读回」时呈现 aware/naive 两种格式。
    对外 API 序列化时由 serializers.iso() 统一补 'Z' 表明这是 UTC。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
