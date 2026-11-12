#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
[[ $# == 3 && $1 =~ ^[0-9a-f]{40}$ && $2 =~ ^sha256:[0-9a-f]{64}$ && $3 =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo 'Usage: yanshi-deploy COMMIT_SHA API_DIGEST WEB_DIGEST' >&2; exit 2;
}
exec 9>/var/lock/yanshi-deploy.lock
flock -n 9 || { echo 'Another release or backup is running.' >&2; exit 1; }
trap 'echo "Release failed. Check logs; database/image rollback is NOT automatic." >&2' ERR
sha=$1
export API_IMAGE="ghcr.io/2667598938/yanshi-api@$2"
export WEB_IMAGE="ghcr.io/2667598938/yanshi-web@$3"
compose() { docker compose -p yanshi -f /opt/yanshi/compose.yaml "$@"; }
[[ -r /etc/yanshi/server.env && -f /opt/yanshi/compose.yaml ]]
compose config --quiet
compose pull
# Check production configuration without printing secrets or changing business data.
compose run --rm --no-deps api python -c '
from app.config import Settings
from importlib.metadata import version
s=Settings(_env_file=None)
assert s.environment=="production" and s.auth_password_only, "Production/password settings required"
assert len(s.jwt_secret)>=48 and len(s.ai_key_enc_secret)>=48, "Strong independent secrets required"
assert s.public_origin=="https://boang.fun" and s.cors_list==["https://boang.fun"], "Unexpected public origin"
assert (s.image_storage=="qiniu" and s.qiniu_access_key and s.qiniu_secret_key and s.qiniu_bucket) or (s.image_storage=="local" and str(s.image_directory).startswith("/var/lib/yanshi/")), "Valid image storage configuration required"
assert s.smtp_host and s.smtp_user and s.smtp_password and not s.mail_console, "SMTP configuration required"
assert len(s.admin_password)>=12 and len(s.admin_password.encode())<=72, "Strong administrator password required"
assert not any("REPLACE_WITH" in str(v) for v in s.model_dump().values()), "Replace template values first"
assert tuple(map(int,version("cryptography").split(".")[:3])) >= (50,0,2), "Security dependency upgrade required"
print("Production configuration preflight passed")'
first_release=true
[[ -f /etc/yanshi/release.env ]] && first_release=false
compose stop web api
database_exists=$(compose run --rm --no-deps api python -c 'from pathlib import Path; print("yes" if Path("/var/lib/yanshi/prod.sqlite").exists() else "no")')
if [[ $database_exists == yes ]]; then
  compose run --rm --no-deps -v /var/backups/yanshi:/backup api \
    python scripts/backup.py --output /backup --keep 14
fi
compose run --rm --no-deps api python -m alembic upgrade head
if [[ $first_release == true ]]; then
  compose run --rm --no-deps api python -m app.seed --quiet
fi
compose up -d --force-recreate --wait --wait-timeout 120 api web
curl --fail --silent --show-error http://127.0.0.1:18080/health/ready
if [[ -f /etc/yanshi/release.env ]]; then
  cp /etc/yanshi/release.env /etc/yanshi/previous-release.env
fi
printf 'RELEASE_SHA=%s\nAPI_IMAGE=%s\nWEB_IMAGE=%s\n' "$sha" "$API_IMAGE" "$WEB_IMAGE" > /etc/yanshi/release.env.new
mv /etc/yanshi/release.env.new /etc/yanshi/release.env
echo
echo "YANSHI_DEPLOY_OK $sha"
