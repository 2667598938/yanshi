#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $(id -u) == 0 ]] || exit 1
exec 9>/var/lock/yanshi-deploy.lock
flock -w 120 9
docker compose --env-file /etc/yanshi/release.env -p yanshi -f /opt/yanshi/compose.yaml \
  run --rm --no-deps -v /var/backups/yanshi:/backup api \
  python scripts/backup.py --output /backup --keep 14
# This only creates local DB backups. Configure and monitor an independent off-host copy.
