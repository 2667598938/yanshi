import json
import zipfile
import pytest
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
