"""SQLite一致性快照、文件校验清单，以及只恢复到新目录的可演练恢复。"""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from sqlalchemy.engine import make_url


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''): digest.update(block)
    return digest.hexdigest()


def create_backup(settings, output):
    if not settings.is_sqlite: raise ValueError('此工具只备份SQLite；MySQL请使用事务一致性数据库备份工具')
    source = Path(make_url(settings.database_url).database).resolve()
    if not source.is_file(): raise ValueError('数据库文件不存在')
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    destination = output / f'yanshi-backup-{stamp}.zip'
    with tempfile.TemporaryDirectory(prefix='yanshi-backup-') as scratch:
        snapshot = Path(scratch) / 'database.sqlite'
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(snapshot)) as dst:
            src.backup(dst)
        files = {'database.sqlite': snapshot}
        uploads = Path(settings.image_directory).resolve()
        if settings.image_storage == 'local' and uploads.exists():
            for path in uploads.rglob('*'):
                if path.is_file() and not path.is_symlink():
                    files['uploads/' + path.relative_to(uploads).as_posix()] = path
        manifest = {'format': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
            'storage': settings.image_storage, 'objects_included': settings.image_storage == 'local',
            'files': {name: {'sha256': sha256(path), 'bytes': path.stat().st_size} for name, path in files.items()}}
        try:
            with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
                for name, path in files.items(): archive.write(path, name)
                archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return destination


def verify_and_restore(archive_path, target=None):
    target = Path(target).resolve() if target else None
    if target and target.exists(): raise ValueError('恢复目标必须是尚不存在的新目录，禁止覆盖现有数据')
    if target and not target.parent.is_dir(): raise ValueError('恢复目标的父目录不存在')
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        if len(entries) > 100000 or sum(e.file_size for e in entries) > 10 * 1024 ** 3:
            raise ValueError('备份超过校验上限（10GB/10万项）')
        names = [e.filename for e in entries]
        if len(names) != len(set(names)): raise ValueError('备份包含重复文件名')
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in entry.filename or ':' in entry.filename:
                raise ValueError('备份包含非法路径')
            if (entry.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('备份不允许符号链接')
        if 'manifest.json' not in names: raise ValueError('备份缺少校验清单')
        if archive.getinfo('manifest.json').file_size > 20 * 1024 ** 2: raise ValueError('校验清单过大')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 1 or not isinstance(manifest.get('files'), dict): raise ValueError('备份格式不支持')
        if set(names) != set(manifest['files']) | {'manifest.json'} or 'database.sqlite' not in manifest['files']:
            raise ValueError('备份文件与清单不一致')
        # 所有内容先解到独立临时目录，完成校验后才创建最终恢复目录。
        with tempfile.TemporaryDirectory(prefix='.yanshi-restore-', dir=target.parent if target else None) as scratch:
            staging = Path(scratch) / 'data'; staging.mkdir()
            for name, expected in manifest['files'].items():
                path = staging.joinpath(*PurePosixPath(name).parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as src, path.open('xb') as dst: shutil.copyfileobj(src, dst)
                if path.stat().st_size != expected['bytes'] or sha256(path) != expected['sha256']:
                    raise ValueError('备份文件校验失败：' + name)
            with closing(sqlite3.connect((staging / 'database.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('数据库完整性校验失败')
                if db.execute('PRAGMA foreign_key_check').fetchone(): raise ValueError('数据库外键校验失败')
            if target: staging.rename(target)
    return manifest
