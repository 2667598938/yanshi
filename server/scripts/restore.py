"""校验备份或恢复到新目录；不会覆盖正在使用的数据库。"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.backup import verify_and_restore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    parser.add_argument('--target', help='尚不存在的新目录；省略时只校验')
    args = parser.parse_args()
    try:
        manifest = verify_and_restore(args.archive, args.target)
        print(json.dumps({'verified': True, 'restored': bool(args.target),
            'storage': manifest['storage'], 'objects_included': manifest['objects_included']}, ensure_ascii=False))
    except Exception as error:
        print('校验或恢复失败：' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
