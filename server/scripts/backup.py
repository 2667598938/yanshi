"""SQLite在线一致性快照+本地图片+SHA256清单；七牛对象需另行开启版本与独立备份。"""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import Settings
from app.services.backup import create_backup

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT / 'data' / 'backups'))
    parser.add_argument('--keep', type=int, default=14)
    args = parser.parse_args()
    if args.keep < 1: parser.error('--keep必须至少为1')
    try:
        path = create_backup(Settings(), args.output)
        for old in sorted(path.parent.glob('yanshi-backup-*.zip'))[:-args.keep]: old.unlink()
        print('备份完成：' + str(path))
    except Exception as error:
        print('备份失败：' + str(error), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__': raise SystemExit(main())
