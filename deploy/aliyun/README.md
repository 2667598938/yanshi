# 阿里云 ECS 部署指南（研时 yanshi）

适用：阿里云 ECS 2核2G、Ubuntu 24.04、公网 IP 139.196.205.43。
域名 duzhi.xin 已在阿里云完成备案，同厂商换机无需重新备案，只改解析。
本目录支持首次部署及现有 Aliyun Compose 安装的更新。现有站点直接看第 10 节。

---

## 1. 配置安全组（阿里云控制台）

在实例的安全组入方向只放行以下端口：

| 端口 | 协议 | 来源 | 用途 |
| --- | --- | --- | --- |
| 22 | TCP | 建议限制为你的固定 IP | SSH 登录 |
| 80 | TCP | 0.0.0.0/0 | HTTP、certbot 验证 |
| 443 | TCP | 0.0.0.0/0 | HTTPS |

18080 只绑定在 127.0.0.1，不要在安全组放行。

## 2. 系统更新与 Docker 安装

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
docker --version && docker compose version
```

## 3. 配置 2G swap（小内存必备）

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

## 4. 目录与配置文件

```bash
sudo mkdir -p /opt/yanshi /etc/yanshi
sudo cp deploy/aliyun/compose.yaml /opt/yanshi/compose.yaml
sudo cp deploy/aliyun/server.env.example /etc/yanshi/server.env
sudo chmod 600 /etc/yanshi/server.env
```

生成两个独立的强密钥（各执行一次，把输出分别填入 server.env）：

```bash
openssl rand -hex 48   # 填 JWT_SECRET
openssl rand -hex 48   # 填 AI_KEY_ENC_SECRET
```

编辑 `/etc/yanshi/server.env`，至少替换这些字段：

- `JWT_SECRET`、`AI_KEY_ENC_SECRET`：上面生成的值，两者必须不同。
- `ADMIN_EMAIL`、`ADMIN_PASSWORD`：管理员账号，密码至少 12 位。
- `SMTP_USER`、`SMTP_PASSWORD`、`SMTP_FROM`：QQ 邮箱及授权码（用于发验证码）。
- `IMAGE_STORAGE=local` 已默认，七牛字段留空即可。
- 确认所有 `REPLACE_WITH_*` 占位都已替换。

## 5. 首次部署

打开 GitHub Actions 中成功的 `Build and release Azure images` 运行记录，从同一个 Summary 复制 `Commit`、`API` 和 `Web` 三个值。

```bash
sudo bash deploy/aliyun/deploy.sh '<Commit>' '<API sha256:…>' '<Web sha256:…>'
```

脚本会自动：拉取镜像 → 数据库迁移 → 首次 seed 管理员 → 启动容器 → 健康检查。
看到 `YANSHI_DEPLOY_OK` 即成功。此时容器只监听本机 127.0.0.1:18080。

## 6. 宿主 Nginx 反向代理

已有 HTTPS 站点时，在现有站点配置中将研时的 `location /` 代理段替换为下面的 `include`。保留现有证书路径、监听端口、域名和 Certbot 配置。共享片段包含普通请求和音视频房间的 WebSocket 信令代理。

```bash
sudo install -m 0644 deploy/azure/nginx-host-location.conf /etc/nginx/snippets/yanshi-proxy.conf
```

仅在首次创建站点时运行下列命令。

```bash
sudo apt install -y nginx
sudo install -m 0644 deploy/azure/nginx-host-location.conf /etc/nginx/snippets/yanshi-proxy.conf
sudo tee /etc/nginx/sites-available/yanshi >/dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name duzhi.xin;

    include /etc/nginx/snippets/yanshi-proxy.conf;
}
EOF
sudo ln -sf /etc/nginx/sites-available/yanshi /etc/nginx/sites-enabled/yanshi
```

新增或修改代理后执行 `sudo nginx -t && sudo systemctl reload nginx`。

## 7. 切换域名解析

在域名控制台把 `duzhi.xin` 的 A 记录改为 `139.196.205.43`，删除旧的 A 记录。
等待解析生效（可用 `dig +short duzhi.xin` 确认返回新 IP）。

## 8. 申请 HTTPS 证书

解析生效后执行，按提示输入邮箱、同意条款：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d duzhi.xin --redirect
```

Certbot 会配置 443、HTTP 跳转及证书续期。安全响应头由 Web 容器生成。已有站点曾按旧指南引用 `/etc/nginx/security-headers.conf` 时，从研时宿主站点配置中移除该引用，再检查配置并重载。

## 9. 上线验证

- 打开 https://duzhi.xin ，确认锁形图标、无证书告警。
- 用管理员账号登录，确认页脚显示 ICP 号并可点击跳转。
- 上传一张图片，然后在服务器执行 `sudo ls /var/lib/docker/volumes/yanshi-data/_data/uploads`，
  确认文件确实落在持久卷，而不是容器临时层。
- 健康检查：`curl -f http://127.0.0.1:18080/health/ready`。

## 10. 后续更新代码

代码合并到 main 并完成镜像发布后，从对应运行记录复制第 5 节的三个值。保留现有 `/etc/yanshi/server.env` 和数据卷。

```bash
sudo install -m 0644 deploy/aliyun/compose.yaml /opt/yanshi/compose.yaml
sudo bash deploy/aliyun/deploy.sh '<Commit>' '<API sha256:…>' '<Web sha256:…>'
```

更新脚本先拉取镜像，再短暂停服。已有数据库会先备份并校验 SQLite 和本地图片，随后才执行数据库迁移。备份或校验失败会停止更新并尝试恢复原服务。

如果迁移或启动失败，检查日志及 `/var/backups/yanshi` 中本次备份。回滚前应在新目录演练恢复数据库及图片，再用 `/etc/yanshi/previous-release.env` 记录的镜像恢复服务。首次从旧模板升级时，该文件记录的是当前机器上的镜像 ID，演练结束前保留这些镜像。

## 11. 定时备份

迁移前备份保存在 `/var/backups/yanshi`，保留最近 14 份，包含 SQLite 和本地图片。七牛图片需要独立备份。

```bash
sudo install -m 0750 deploy/azure/backup.sh /usr/local/sbin/yanshi-backup
sudo install -m 0644 deploy/azure/yanshi-backup.service deploy/azure/yanshi-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yanshi-backup.timer
sudo systemctl start yanshi-backup.service
sudo journalctl -u yanshi-backup.service -n 20 --no-pager
```

定期做磁盘快照或把已校验的备份复制到异地，避免服务器故障时同时丢失原数据和备份。

## 12. 现有站点的运营配置

在 `/etc/yanshi/server.env` 设置 `AUTH_EMAIL_DOMAINS=`、`AUTH_QQ_NUMERIC_ONLY=false` 与 `ACCOUNT_MAX_USERS=300`。现有显式环境变量优先于代码默认值。邮箱注册开关继续由管理后台控制，放开前分别向 QQ、163 和学校邮箱发送测试验证码。

生产环境缺少 TURN 地址或密钥时自动隐藏 `av_room`。准备同地区的 coturn，在服务端使用共享密钥认证、限制中继端口范围和带宽。云主机有公网/私网映射时配置 coturn 的 `external-ip`，安全组与防火墙放行监听端口和指定的 UDP 中继端口。把可达的 STUN 地址填入 `ROOM_ICE_SERVERS`，TURN 地址填入 `ROOM_TURN_URLS`，把同一共享密钥写入私有配置的 `ROOM_TURN_SECRET`。跨 Wi-Fi 与蜂窝网络验收双向收音和视频后再开放。参见 [coturn 配置参考](https://github.com/coturn/coturn/blob/master/examples/etc/turnserver.conf)。

给 `https://duzhi.xin/health/ready` 配置 HTTPS 拨测并对连续失败和证书到期报警。API 日志含请求 ID、路由模板、状态码和耗时。先收集一周 `csp_report` 日志，验证登录、数学渲染、图片上传、离线刷新和音视频，再评估把 CSP 改成强制模式。

已有商业证书的站点可以先用 Certbot 的 `certonly --webroot` 单独申请证书。请先确认 HTTP 的 ACME 路径由指定目录提供，签发成功后再把现有 HTTPS 站点切到新证书，并运行 `nginx -t`。切换后用 `certbot renew --dry-run` 验证续期，并设置续期成功时重载 Nginx 的 deploy hook。参见 [Certbot 续期文档](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates)。

清理前记录当前和上一版镜像 ID，核对回滚镜像仍在，再删除明确废弃的镜像。旧部署目录应先确认已脱离 Nginx、容器、定时任务和备份配置，并保留可恢复副本。

## 日常运维命令

```bash
sudo docker compose -p yanshi -f /opt/yanshi/compose.yaml --env-file /etc/yanshi/release.env ps
sudo docker compose -p yanshi -f /opt/yanshi/compose.yaml --env-file /etc/yanshi/release.env logs -f
sudo docker stats
```
