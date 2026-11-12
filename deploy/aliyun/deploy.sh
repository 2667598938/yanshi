#!/usr/bin/env bash
# 阿里云小规格实例部署/更新脚本：拉取最新 :main 镜像并重启。
# 首次使用前请先安装 Docker、放好 /etc/yanshi/server.env 与 /opt/yanshi/compose.yaml。
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
exec 9>/var/lock/yanshi-deploy.lock
flock -n 9 || { echo 'Another release is running.' >&2; exit 1; }
compose() { docker compose -p yanshi -f /opt/yanshi/compose.yaml "$@"; }
[[ -r /etc/yanshi/server.env && -f /opt/yanshi/compose.yaml ]]
compose config --quiet
compose pull
# 首次启动需要先跑数据库迁移；镜像内已含 Alembic，升级失败则中止，不会强行上线。
compose run --rm --no-deps api python -m alembic upgrade head
compose up -d --force-recreate --wait --wait-timeout 120
curl --fail --silent --show-error http://127.0.0.1:18080/health/ready
echo
echo "YANSHI_DEPLOY_OK"
