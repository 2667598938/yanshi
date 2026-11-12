import json
import zipfile
import pytest
from app.models import Attachment
from app.services.backup import create_backup, verify_and_restore


def test_backup_integrity_restore_and_no_overwrite(client, tmp_path):
    settings = client.app.state.settings
    settings.image_directory.mkdir(parents=True, exist_ok=True)
    (settings.image_directory / 'sample.jpg').write_bytes(b'local-image-fixture')
    path = create_backup(settings, tmp_path / 'backups')
    assert verify_and_restore(path)['objects_included']
    target = tmp_path / 'restored'
    verify_and_restore(path, target)
    assert (target / 'database.sqlite').is_file()
    assert (target / 'uploads' / 'sample.jpg').read_bytes() == b'local-image-fixture'
    with pytest.raises(ValueError, match='禁止覆盖'): verify_and_restore(path, target)
    settings.image_storage = 'qiniu'
    cloud_backup = create_backup(settings, tmp_path / 'backups')
    cloud_manifest = verify_and_restore(cloud_backup)
    assert not cloud_manifest['objects_included']
    assert cloud_manifest['local_objects_included']
    assert set(cloud_manifest['files']) == {'database.sqlite', 'uploads/sample.jpg'}


def test_restore_rejects_tampering_and_traversal_without_partial_output(client, tmp_path):
    path = create_backup(client.app.state.settings, tmp_path / 'backups')
    corrupt = tmp_path / 'corrupt.zip'
    with zipfile.ZipFile(path) as original, zipfile.ZipFile(corrupt, 'w') as archive:
        for name in original.namelist():
            archive.writestr(name, b'corrupted' if name == 'database.sqlite' else original.read(name))
    target = tmp_path / 'bad-restore'
    with pytest.raises(ValueError, match='校验失败'): verify_and_restore(corrupt, target)
    assert not target.exists()
    attack = tmp_path / 'attack.zip'
    with zipfile.ZipFile(attack, 'w') as archive:
        archive.writestr('../escape', 'bad')
        archive.writestr('manifest.json', json.dumps({'format': 1, 'files': {}}))
    with pytest.raises(ValueError, match='非法路径'): verify_and_restore(attack, target)
    assert not (tmp_path / 'escape').exists()


def test_backup_and_restore_require_referenced_local_images(client, tmp_path):
    settings = client.app.state.settings
    key = 'mistake/1/sample.jpg'
    original_bytes = b'local-image-fixture'
    with client.app.state.session_factory() as db:
        db.add(Attachment(object_key=key, uploader_id=1, biz_type='mistake', size_bytes=len(original_bytes)))
        db.commit()
    image = settings.image_directory / key
    image.parent.mkdir(parents=True)
    image.write_bytes(original_bytes)
    path = create_backup(settings, tmp_path / 'backups')
    assert verify_and_restore(path)['objects_included']

    incomplete = tmp_path / 'incomplete.zip'
    with zipfile.ZipFile(path) as original, zipfile.ZipFile(incomplete, 'w') as archive:
        manifest = json.loads(original.read('manifest.json'))
        del manifest['files']['uploads/' + key]
        archive.writestr('database.sqlite', original.read('database.sqlite'))
        archive.writestr('manifest.json', json.dumps(manifest))
    target = tmp_path / 'restore'
    with pytest.raises(ValueError, match='数据库引用的本地附件'):
        verify_and_restore(incomplete, target)
    assert not target.exists()
    image.write_bytes(original_bytes[:4])
    with pytest.raises(ValueError, match='附件大小与数据库记录不一致'):
        create_backup(settings, tmp_path / 'backups')
    image.unlink()
    with pytest.raises(ValueError, match='数据库引用的本地附件'):
        create_backup(settings, tmp_path / 'backups')
