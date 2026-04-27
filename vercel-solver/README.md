# vercel-solver

这是一个适合部署到 Vercel 的无状态同步求解服务，新项目与仓库原有 `solver-web` 完全隔离，只提供 `POST /solve` 和 `GET /health`。

## 本地启动

```powershell
cd vercel-solver
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
hypercorn app:app
```

默认监听 `http://127.0.0.1:8000`。

## 请求示例

```json
{
  "clientKey": "swk_demo_key",
  "task": {
    "type": "TurnstileTaskProxyless",
    "websiteURL": "https://example.com",
    "websiteKey": "0x4AAAAAAA"
  }
}
```

成功时返回：

```json
{
  "errorId": 0,
  "status": "ready",
  "solution": {
    "token": "token-value"
  }
}
```

## 环境变量

- `CLIENT_KEYS`: 逗号分隔的静态 API Key 列表
- `SOLVER_NODE_URLS`: 逗号分隔的 solver 节点列表
- `SOLVER_MAX_WAIT_SECONDS`: 单次等待 solver 结果的最长秒数
- `OUTBOUND_PROXY_URL`: 可选，出站代理地址
- `OUTBOUND_NO_PROXY`: 直连白名单，默认 `localhost,127.0.0.1,::1`

## Vercel 部署

把 `vercel-solver/` 作为独立 Project Root 导入 Vercel 即可。`app.py` 暴露单个 Quart `app`，`vercel.json` 已设置 Python Function 的 `maxDuration=60`。如果你把 `SOLVER_MAX_WAIT_SECONDS` 调大到 50 秒以上，需要同步提高 `maxDuration`。

## 已废弃接口

以下路径会固定返回 `410`：

- `POST /createTask`
- `POST /getTaskResult`
- `/admin/*`
