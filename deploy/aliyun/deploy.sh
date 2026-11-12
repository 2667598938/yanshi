#!/usr/bin/env bash
# 使用同一次 GitHub 构建的镜像；先验证备份，再迁移并启动。
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
if [[ $# != 3 || ! $1 =~ ^[a-f0-9]{40}$ || ! $2 =~ ^sha256:[a-f0-9]{64}$ || ! $3 =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo 'Usage: deploy.sh COMMIT_SHA API_DIGEST WEB_DIGEST (from the same GitHub build)' >&2
  exit 1
fi
umask 077
exec 9>/var/lock/yanshi-deploy.lock
flock -n 9 || { echo 'Another release is running.' >&2; exit 1; }
export API_IMAGE="ghcr.io/2667598938/yanshi-api@$2"
export WEB_IMAGE="ghcr.io/2667598938/yanshi-web@$3"
compose() { docker compose -p yanshi -f /opt/yanshi/compose.yaml "$@"; }
[[ -r /etc/yanshi/server.env && -f /opt/yanshi/compose.yaml ]]
compose config --quiet
images=$(compose config --images)
if ! grep -Fxq "$API_IMAGE" <<< "$images" || ! grep -Fxq "$WEB_IMAGE" <<< "$images"; then
  echo 'Install the current deploy/aliyun/compose.yaml before updating.' >&2
  exit 1
fi
compose pull
database_exists=$(compose run -T --rm --no-deps api python -c '
from pathlib import Path
from sqlalchemy.engine import make_url
from app.config import Settings
settings = Settings()
if settings.environment != "production" or not settings.is_sqlite:
    raise SystemExit("Aliyun deployment expects production with SQLite")
database = Path(make_url(settings.database_url).database).resolve()
if Path("/var/lib/yanshi") not in database.parents:
    raise SystemExit("SQLite database must be on the yanshi-data volume")
print("yes" if database.is_file() else "no")
')
[[ $database_exists == yes || $database_exists == no ]]

running_services=$(compose ps --status running --services api web)
stopped=false
migration_started=false
release_file=$(mktemp /etc/yanshi/.release.XXXXXX)
cleanup() {
  local status=$?
  rm -f -- "$release_file"
  if (( status != 0 )) && [[ $stopped == true ]]; then
    if [[ $migration_started == false && -n $running_services ]]; then
      mapfile -t services <<< "$running_services"
      compose start "${services[@]}" || true
    elif [[ $migration_started == true ]]; then
      echo 'Release failed after migration began. Check /var/backups/yanshi and the previous release before restoring.' >&2
    fi
  fi
}
trap cleanup EXIT
printf 'COMMIT_SHA=%s\nAPI_IMAGE=%s\nWEB_IMAGE=%s\n' "$1" "$API_IMAGE" "$WEB_IMAGE" > "$release_file"

# 停止写入后再拍数据库及图片的同一份快照。
stopped=true
compose stop web api
if [[ $database_exists == yes ]]; then
  backup_dir=/var/backups/yanshi
  install -d -m 0700 -o 10001 -g 10001 "$backup_dir"
  compose run -T --rm --no-deps -e TMPDIR=/backup -v "$backup_dir:/backup" api \
    python scripts/backup.py --output /backup --keep 14 --verify
fi
if [[ -f /etc/yanshi/release.env ]]; then
  install -m 0600 /etc/yanshi/release.env /etc/yanshi/previous-release.env
elif [[ ! -f /etc/yanshi/previous-release.env ]]; then
  # 兼容仍使用 :main 的旧安装，记录正在使用的本地镜像 ID。
  previous_api=$(compose ps -aq api)
  previous_web=$(compose ps -aq web)
  if [[ -n $previous_api && -n $previous_web ]]; then
    previous_api=$(docker inspect --format '{{.Image}}' "$previous_api")
    previous_web=$(docker inspect --format '{{.Image}}' "$previous_web")
    printf 'API_IMAGE=%s\nWEB_IMAGE=%s\n' "$previous_api" "$previous_web" > /etc/yanshi/previous-release.env
  fi
fi
migration_started=true
compose run -T --rm --no-deps api python -m alembic upgrade head
admin_exists=$(compose run -T --rm --no-deps api python -c '
from sqlalchemy import select
from app.config import Settings
from app.database import make_database
from app.models import User
_, sessions = make_database(Settings().database_url)
with sessions() as db:
    print("yes" if db.scalar(select(User.id).where(User.role == "admin").limit(1)) else "no")
')
[[ $admin_exists == yes || $admin_exists == no ]]
if [[ $admin_exists == no ]]; then
  compose run -T --rm --no-deps api python -m app.seed --quiet
fi
compose up -d --pull never --force-recreate --wait --wait-timeout 120
curl --fail --silent --show-error http://127.0.0.1:18080/health/ready
mv -f -- "$release_file" /etc/yanshi/release.env
echo
echo "YANSHI_DEPLOY_OK"
