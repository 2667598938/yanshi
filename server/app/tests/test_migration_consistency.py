from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from app.config import Settings
from app.database import make_database
from app.models import User
from app.seed import seed
from app.time import utcnow


def test_upgrade_legacy_null_mask_preserves_ciphertext_and_schema_matches(tmp_path, monkeypatch):
    server = Path(__file__).resolve().parents[2]
    url = 'sqlite:///' + (tmp_path / 'migration.sqlite').as_posix()
    monkeypatch.setenv('DATABASE_URL', url)
    config = Config(str(server / 'alembic.ini'))
    config.set_main_option('script_location', str(server / 'alembic'))
    command.upgrade(config, 'd7f9b1c3e5a7')
    engine, sessions = make_database(url)
    with sessions() as db:
        seed(db, Settings(_env_file=None, database_url=url, admin_email='migration@test.com',
            admin_password='Migration2028'), echo=lambda *args: None)
        db.flush()
        uid = db.scalar(select(User.id).where(User.email == 'migration@test.com'))
        db.execute(text('INSERT INTO user_ai_keys (user_id,provider,base_url,model,key_cipher,key_mask,updated_at) '
            'VALUES (:uid,:provider,:base,:model,:cipher,NULL,:now)'), {'uid': uid, 'provider': 'deepseek',
                'base': 'https://api.deepseek.com/v1', 'model': 'test-model',
                'cipher': 'unchanged-ciphertext-fixture', 'now': utcnow()})
        db.commit()
    command.upgrade(config, 'head')
    with engine.connect() as connection:
        row = connection.execute(text('SELECT key_mask,key_cipher FROM user_ai_keys WHERE user_id=:uid'), {'uid': uid}).one()
        assert row == ('', 'unchanged-ciphertext-fixture')
    command.check(config)
    command.downgrade(config, 'd7f9b1c3e5a7')
    command.upgrade(config, 'head')
    command.check(config)
    engine.dispose()
