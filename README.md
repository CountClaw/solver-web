# solver-web

`solver-web` 是一个面向 Turnstile 的类 YesCaptcha 服务层，包含以下组件：

- `apps/api`：对外兼容 `createTask/getTaskResult`
- `apps/worker`：异步消费队列并调用 solver 节点
- `apps/admin`：轻量后台 API（Key 管理、任务查看、网络代理配置）
- `core`：共享配置、数据库、限流、队列、代理和 solver 调度

## 1. 快速启动（本地）

```powershell
cd D:\Data\code\orchestrator-projects\grok\grok-protocol\solver-web
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

启动 Redis 后，分别开 3 个终端：

```powershell
hypercorn --bind 0.0.0.0:8080 apps.api.app:app
```

```powershell
hypercorn --bind 0.0.0.0:8090 apps.admin.app:app
```

```powershell
python -m apps.worker.main
```

## 2. Docker 启动

```bash
cp .env.example .env
docker compose up -d --build
```

## 3. 核心接口

- `POST /createTask`
  - 请求体示例：
  - `{"clientKey":"swk_xxx","task":{"type":"TurnstileTaskProxyless","websiteURL":"https://example.com","websiteKey":"0x..."} }`
- `POST /getTaskResult`
  - 请求体示例：
  - `{"clientKey":"swk_xxx","taskId":"..."}`

## 4. 管理后台接口

- `GET /admin/keys`
- `POST /admin/keys`
- `PATCH /admin/keys/{id}`
- `GET /admin/tasks`
- `GET /admin/solvers`
- `GET /admin/settings/network`
- `PUT /admin/settings/network`

所有 `/admin/*` 请求都需要请求头：`X-Admin-Token: <ADMIN_TOKEN>`。

## 5. 代理策略

- 全局代理在 `PUT /admin/settings/network` 中配置。
- 请求路径固定为：优先使用后台代理；若代理连接失败则自动回退直连。
- `noProxy` 默认：`localhost,127.0.0.1,::1`。

