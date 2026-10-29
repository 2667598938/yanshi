# Azure Ubuntu 24.04 部署与恢复

适配：4vCPU/16GiB/64GiB，宿主已有Nginx 1.24、Certbot和boang.fun/www证书，SSH限定来源IP。当前账号总数上限100、使用SQLite单worker；不用安装宿主Python、Node、Java、MySQL或宝塔。

流向：浏览器HTTPS → **已有宿主Nginx** → `127.0.0.1:18080` → web容器 → api容器8000 → 持久卷/七牛/SMTP/本人AI服务商。容器不发布80/443或api8000，既有证书与续期保留。

## 发布前门槛

- 代码经PR进入dev，再发布到main；等待main的完整CI，不部署移动分支或失败提交。CI包括依赖审计、单元测试、迁移、镜像构建、Nginx配置、代理、安全头、生产密码登录、重启、卷与备份恢复。
- Python直接版本在`server/requirements.txt`，完整解析与文件哈希在`server/requirements.lock`。安装用`pip install --require-hashes -r requirements.lock`；更新直接版本后，在干净Python3.12环境重新生成hash lock并验证Linux/Windows。cryptography已固定50.0.2，旧46.0.3密文有兼容测试。不要单独在服务器临时升级依赖。
- Action固定完整commit，API与web制品记录digest。`release-azure.yml`只跟随main成功CI，默认仅构建；`DEPLOY_ENABLED=true`才会部署。构建/部署前均拒绝过期main SHA。
- 当前私有仓库规则集功能受GitHub套餐限制，保护能力需核对；保持私有并限制写权限，默认先人工发布。无需为此公开仓库。不要把存在CI等同于强制合并门禁。

## 1. 检查服务器，不覆盖现有站点

```bash
cat /etc/os-release
uname -m
df -h
sudo ss -lntp
sudo nginx -t
sudo certbot certificates
sudo systemctl list-timers --all
command -v docker || true
sudo systemctl status docker --no-pager || true
```

本机查看`sudo nginx -T`，找到真正生效的boang.fun站点并备份。不要把完整环境文件、私钥或密码贴到Issue/聊天。确认18080未占用；如果已有旧yanshi.service或其他业务，先确认数据位置，不能两个启动器写同一SQLite。

宿主需能出站访问GHCR、Docker镜像源、Azure管理端点、七牛、SMTP和所选AI服务商。Indonesia到国内供应商的延迟、地域权限与邮件端口须从实际服务器验收。

## 2. 安装Docker（确认未安装且无冲突后）

使用[Docker官方Ubuntu仓库](https://docs.docker.com/engine/install/ubuntu/)，不卸载已有运行时或改动Nginx。

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

Compose需2.30+，支持`env_file.format: raw`。保持SSH白名单，不额外开放18080/8000；不能把`127.0.0.1:18080:8080`改为公网绑定。Docker管理命令使用sudo，不默认授予普通账号docker组权限。

## 3. 安装控制文件与配置

通过现有SSH/SCP，把已验收发布版本的`deploy/azure/`传到服务器。从该目录执行：

```bash
sudo install -d -m 0755 /opt/yanshi
sudo install -d -m 0700 /etc/yanshi
sudo install -d -o 10001 -g 10001 -m 0700 /var/backups/yanshi
sudo install -m 0644 compose.yaml /opt/yanshi/compose.yaml
sudo install -m 0750 deploy.sh /usr/local/sbin/yanshi-deploy
sudo install -m 0750 backup.sh /usr/local/sbin/yanshi-backup
sudo install -m 0600 server.env.example /etc/yanshi/server.env
sudoedit /etc/yanshi/server.env
```

新库用两次`openssl rand -hex 48`生成独立JWT_SECRET与AI_KEY_ENC_SECRET；在服务器填写，不提交Git或镜像。填真实管理员强密码、SMTP授权码、七牛**私有**bucket与地域，替换全部REPLACE_WITH。raw文件直接写字面值，无包围引号。内测保持AUTH_PASSWORD_ONLY=true，注册关闭，账号上限100，视频房型关闭。

容器以10001身份读写卷`yanshi-data`，新卷自动继承镜像内目录所有权；不要改卷名或用`down -v`删除数据。root文件系统只读，临时文件在受限tmpfs。备份目录所有者必须10001，否则备份会失败。

### 如果保留现有数据

先停旧服务写入，生成并校验旧库备份。在新环境恢复`database.sqlite`及`uploads/`到隔离目录/卷，改数据库文件名为配置中的`prod.sqlite`并核对10001所有权。保留每条附件原object_key、storage_backend与目录层级；代码已按每条附件实际后端读取、给AI传图和回收，允许旧local图片与新qiniu上传并存。备份也包含遗留本地图片，远端对象仍需独立备份。

保留原加密主密钥；旧AI_KEY_ENC_SECRET为空时使用的加密材料是旧JWT_SECRET（或原data/jwt.key），应把该原值安全填入新AI_KEY_ENC_SECRET。不能给旧数据库随意换一把主密钥。先隔离验证密文与图片，再切正式卷。发布脚本对已有SQLite先备份；首次seed幂等，不覆盖已有账号密码，但保留的ADMIN_EMAIL应与原管理员对应。

不在首次发布脚本自动导入任何本地预览数据，不会清空服务器卷。不要在用户仍写入时直接复制SQLite主文件而漏掉WAL，应使用一致性快照。

## 4. 获取镜像并首次发布

GitHub构建job使用GITHUB_TOKEN推GHCR。服务器拉私有镜像时，使用专用、限期、仅`read:packages`的PAT classic，通过`sudo docker login ghcr.io --username 2667598938 --password-stdin`输入。不要把Token写进命令参数、仓库或工作流正文；限制root Docker凭据文件权限并轮换，条件允许时使用凭据助手。[官方认证说明](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)。

从GitHub发布工作流摘要取得完整commit及API/web digest。保持DEPLOY_ENABLED未设置或false，先SSH手动发布：

```bash
sudo /usr/local/sbin/yanshi-deploy <40位commit> sha256:<API的64位摘要> sha256:<WEB的64位摘要>
curl --fail http://127.0.0.1:18080/health/ready
sudo docker compose --env-file /etc/yanshi/release.env -p yanshi -f /opt/yanshi/compose.yaml ps
```

必须出现`YANSHI_DEPLOY_OK <commit>`。脚本会检查生产模式/密码开关/域名/强密钥/配置/依赖；已有库先停写备份，再迁移；首次seed不会在发布日志打印管理员密码。发布有短维护窗口，失败不自动倒退数据库，保留日志等待处理。

字段完整的预检不能证明bucket私有、SMTP送达或AI服务可用，首次发布还必须走真实业务验收。

## 5. 接入已有Nginx和HTTPS

将`nginx-host-location.conf`合并进**现有boang.fun的443站点**：保留listen/server_name/证书路径/Certbot管理部分；替换已有同名location /，不要重复定义，也不要添加第二套冲突的80/443站点。已有client_max_body_size只保留一份有效配置。80端口及ACME挑战路径按原方案保留。

www建议在现有HTTPS站点重定向到`https://boang.fun$request_uri`，使账号、本地库和Cookie统一在主域。按现有server块结构合并，不盲目新建冲突站点。主域PUBLIC_ORIGIN与CORS保持示例值。

```bash
sudo nginx -t
sudo systemctl reload nginx
curl --fail https://boang.fun/health/ready
curl -I https://boang.fun/index.html
curl -I https://boang.fun/sw.js
curl -I https://www.boang.fun/
sudo ss -lntp
```

nginx -t失败不reload。核对静态安全头、SPA深链接、缺失assets返回404、index/sw不缓存旧版本、SSE逐段输出；不要用纯HTTP判断生产Secure Cookie登录是否正常。

Nginx1.24按传统add_header继承规则处理；容器每个带独立缓存头的location均include安全头，不使用新版add_header_inherit。[官方继承规则](https://nginx.org/en/docs/http/ngx_http_headers_module.html)。API仅在专属Compose网络内，信任此网络的web代理；不要给api另开宿主端口或接入不可信容器。[可信代理说明](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)。

## 6. 备份、日志与恢复

```bash
sudo install -m 0644 yanshi-backup.service /etc/systemd/system/yanshi-backup.service
sudo install -m 0644 yanshi-backup.timer /etc/systemd/system/yanshi-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now yanshi-backup.timer
sudo systemctl start yanshi-backup.service
sudo journalctl -u yanshi-backup.service -n 40 --no-pager
sudo systemctl list-timers yanshi-backup.timer
sudo docker compose --env-file /etc/yanshi/release.env -p yanshi -f /opt/yanshi/compose.yaml logs --tail 100 api web
df -h
```

每日UTC03:15左右备份，保留14份，与发布共用锁。容器日志各10MB×3轮转；仍需监控64GiB盘空间、备份失败和证书续期。不要运行全局volume prune清空间。

本机备份不能覆盖磁盘损毁，需要复制到独立存储；七牛远端对象不在SQLite包内，需要另外配置版本保留/独立备份。加密主密钥单独安全保管。

恢复用`server/scripts/restore.py`，先校验路径、哈希、SQLite完整性/外键，并仅恢复到新目录；使用隔离卷/端口和原密钥验证。Docker内可运行`python scripts/restore.py <挂载的包> --target <新目录>`。不要覆盖运行中的库；恢复演练成功后才算备份可用。

当前/上版的commit和镜像digest分别记录在`/etc/yanshi/release.env`与`previous-release.env`。兼容代码回退可用旧digest重新发布；不兼容数据库迁移必须停写，在新卷恢复上版备份及必要对象后验证切换。不要自动alembic downgrade；恢复点之后的新增数据会受影响，应先确认。发布脚本失败不会自动把旧镜像接到已迁移数据库。

## 7. 后续自动部署

保留SSH白名单，采用[Azure OIDC](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)+[VM Run Command](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command)。需要VM Agent正常、出站443可达Azure管理端点。

1. Azure联邦信任subject限定`repo:2667598938/yanshi:ref:refs/heads/main`；权限限定这台VM的读取与RunCommand能力，不授予订阅Owner。此能力能在VM执行高权限脚本，应保护仓库写权限。
2. GitHub仓库Secrets设置AZURE_CLIENT_ID/AZURE_TENANT_ID/AZURE_SUBSCRIPTION_ID；Variables设置AZURE_RESOURCE_GROUP/AZURE_VM_NAME。业务Key只留服务器env，不进入GitHub变量。
3. 首次手动部署、七牛/SMTP/AI、恢复演练通过后，才把DEPLOY_ENABLED设为true。模板不依赖当前私有套餐不支持的受保护environment。若以后改为受保护production环境，须同步修改workflow和OIDC subject。
4. main最新成功CI→依赖审计/构建→按两个digest调用发布脚本→预检/备份/迁移/ready→验证成功标记。GitHub和VM双重串行锁，CLI返回0仍需匹配服务器成功标记。Azure身份配置、真实供应商与生产业务尚需实际服务器验收，CI不会创建云资源或自动填写密钥。

## 首次业务验收

密码登录/刷新/退出及邮件找回；管理员创建成员；账号/VIP不自动入房；好友房间邀请、房主审批、共享确认和跨房间隔离；两设备计时独占、暂停、跨页共学、后台暂离/90秒离线；隐私后端隔离；七牛题图/解析/相册跨设备；AI本人Key/模型/真实SSE/公式/历史/学习摘要/人工确认导入与撤销；重启数据持久、备份与隔离恢复。电脑和手机都要实测。

CI中的生产冒烟只在GitHub临时runner使用伪配置，不调用真实七牛、SMTP或收费模型，不代表上述真实环境验收已经完成。
