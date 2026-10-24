"""研时数据备份：SQLite 一致性快照 + uploads 图片打包为单个 zip。

用法：
    .venv\\Scripts\\python.exe scripts\\backup.py
产物：data/backups/yanshi-backup-YYYYMMDD-HHMMSS.zip
建议：备案上线后用服务器 crontab 每天凌晨执行一次，保留最近 14 份。
"""
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Settings   # noqa: E402

settings = Settings()
if not settings.is_sqlite:
    print('当前不是 SQLite，本脚本仅用于本地/单机 SQLite 备份。')
    sys.exit(1)

db_path = Path(settings.database_url.replace('sqlite:///', '')).resolve()
uploads_dir = Path(settings.image_directory)
out_dir = ROOT / 'data' / 'backups'
out_dir.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
zip_path = out_dir / f'yanshi-backup-{stamp}.zip'
snapshot = out_dir / f'.snapshot-{stamp}.sqlite'

# 1) SQLite 在线一致性快照（.backup 会正确处理 WAL）
src = sqlite3.connect(str(db_path))
dst = sqlite3.connect(str(snapshot))
src.backup(dst)
dst.close()
src.close()

# 2) 打包快照 + uploads
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(snapshot, 'dev.sqlite')
    if uploads_dir.exists():
        for f in uploads_dir.rglob('*'):
            if f.is_file():
                zf.write(f, Path('uploads') / f.relative_to(uploads_dir))

snapshot.unlink(missing_ok=True)

# 3) 仅保留最近 14 份
for old in sorted(out_dir.glob('yanshi-backup-*.zip'))[:-14]:
    old.unlink(missing_ok=True)

print(f'备份完成：{zip_path}  （{zip_path.stat().st_size/1024:.1f} KB）')
