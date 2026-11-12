# 阿里云 ECS 部署指南（研时 yanshi）

适用：阿里云 ECS 2核2G、Ubuntu 24.04、公网 IP 139.196.205.43。
备案已在阿里云完成（豫ICP备2026056816号），同厂商换机无需重新备案，只改解析。
本目录为全新部署，不迁移旧数据。

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

```bash
sudo bash deploy/aliyun/deploy.sh
```

脚本会自动：拉取镜像 → 数据库迁移 → 首次 seed 管理员 → 启动容器 → 健康检查。
看到 `YANSHI_DEPLOY_OK` 即成功。此时容器只监听本机 127.0.0.1:18080。

## 6. 宿主 Nginx 反向代理

```bash
sudo apt install -y nginx
sudo tee /etc/nginx/sites-available/yanshi >/dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name boang.fun;

    client_max_body_size 8m;

    location / {
        proxy_pass http://127.0.0.1:18080;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 180s;
    }
}
EOF
sudo ln -sf /etc/nginx/sites-available/yanshi /etc/nginx/sites-enabled/yanshi
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 7. 切换域名解析

在域名控制台把 `boang.fun` 的 A 记录改为 `139.196.205.43`，删除旧的 A 记录。
等待解析生效（可用 `dig +short boang.fun` 确认返回新 IP）。

## 8. 申请 HTTPS 证书

解析生效后执行，按提示输入邮箱、同意条款：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d boang.fun --redirect
```

certbot 会自动把站点改为 443 并加 HTTP 跳 HTTPS，证书到期自动续期。
完成后把安全头加进 HTTPS server 块：在 `include /etc/nginx/security-headers.conf;` 前先
`sudo cp deploy/azure/security-headers.conf /etc/nginx/security-headers.conf`，再在站点
配置的 server 块内引用，reload 生效。

## 9. 上线验证

- 打开 https://boang.fun ，确认锁形图标、无证书告警。
- 用管理员账号登录，确认页脚显示 ICP 号并可点击跳转。
- 上传一张图片，然后在服务器执行 `sudo ls /var/lib/docker/volumes/yanshi-data/_data/uploads`，
  确认文件确实落在持久卷，而不是容器临时层。
- 健康检查：`curl -f http://127.0.0.1:18080/health/ready`。

## 10. 后续更新代码

代码合并到 main 后，CI 会自动构建并更新 `:main` 镜像。服务器上执行：

```bash
sudo bash deploy/aliyun/deploy.sh
```

## 11. 备份（重要）

本地存储后，图片是服务器上的唯一权威副本，现有备份只覆盖数据库。建议：

- 定期对 `yanshi-data` 卷做快照（阿里云可对系统盘/数据盘创建快照）。
- 或定期把 uploads 目录与数据库打包，下载到本机或异地保存。

## 日常运维命令

```bash
docker compose -p yanshi -f /opt/yanshi/compose.yaml ps      # 查看容器状态
docker compose -p yanshi -f /opt/yanshi/compose.yaml logs -f # 查看日志
docker stats                                                 # 实时内存占用
```
