# 研时前端（yanshi-web）

Vue 3 + Vite 单页应用，移动端优先。开发端口 `27341`，`/api` 代理到本地 `http://127.0.0.1:8000`。

完整安装、后端启动与配置步骤见根目录 [README.md](../README.md)。

## 命令

```bash
npm ci          # 按 lockfile 安装依赖
npm run dev     # 开发服务器 http://localhost:27341
npm run build   # 生产构建，产物在 dist/
npm run preview # 预览构建结果
```

## 目录

```text
src/
├─ api/         后端接口封装（含 SSE 流式请求）
├─ components/  通用组件（TabBar、离线横幅、冲突弹窗等）
├─ db/          Dexie 本地库（学习数据、outbox、离线草稿）
├─ stores/      Pinia（账号、计时、任务、错题、设置）
├─ sync/        同步引擎与社区离线队列
├─ utils/       时间、日期、图片等工具
└─ views/       页面（番茄、统计、自习室、资料、动态、AI、后台…）
```

## 约定

- 学习数据先写 IndexedDB，再经 `sync/` 入队同步；离线可用
- 后端时间统一为 UTC，展示前用 `utils/time.js` 转本地时区，不要直接切字符串
- 接口统一返回 `{ code, message, data }`，业务错误由 `api/http.js` 抛出
