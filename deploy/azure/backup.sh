#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $(id -u) == 0 ]] || exit 1
exec 9>/var/lock/yanshi-deploy.lock
flock -w 120 9
install -d -m 0700 -o 10001 -g 10001 /var/backups/yanshi
docker compose --env-file /etc/yanshi/release.env -p yanshi -f /opt/yanshi/compose.yaml \
  run -T --rm --no-deps -e TMPDIR=/backup -v /var/backups/yanshi:/backup api \
  python scripts/backup.py --output /backup --keep 14 --verify
# This only creates local DB backups. Configure and monitor an independent off-host copy.
