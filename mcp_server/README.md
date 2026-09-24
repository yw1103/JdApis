# JdApis MCP Server（SSE）

将 [JdApis](../README.md) 的京东登录态业务能力，以 **MCP over SSE** 形式暴露给 Cursor / Claude Desktop 等客户端。

本目录是**衍生层**：不修改 `jd_apis/`、`utils/`、`builder/` 等原项目核心代码，下次拉取上游时冲突面积极小。

## 协议与端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/sse` | 建立 SSE 长连接 |
| `POST` | `/messages/` | 客户端投递 JSON-RPC 消息 |
| `GET` | `/health` | 健康检查（非 MCP 协议） |

默认监听：`0.0.0.0:8765`（compose 映射后本机/公网均可访问）。公网暴露带登录态的服务有风险，自行注意。

## 推荐：Docker Compose 一键部署

主流程是 compose：**无需**在宿主机登录，**不要**挂载 `auth.json`，登录态只写容器内 tmpfs，销毁即丢。

在**仓库根目录**：

```bash
docker compose -f mcp_server/docker-compose.yml up -d --build
```

或在 `mcp_server/` 目录：

```bash
docker compose up -d --build
```

`build.context` 为 `..`（仓库根），从 `mcp_server/` 执行同样正确。

国内云主机若构建卡住或 Docker Hub 超时，见下方 [国内云主机构建加速](#国内云主机构建加速腾讯云等)；建议用 `docker compose build --progress=plain` 查看详细进度。

自检：

```bash
curl http://127.0.0.1:8765/health
```

停止（登录态一并丢弃）：

```bash
docker compose -f mcp_server/docker-compose.yml down
```

可选环境变量：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MCP_HOST` | `0.0.0.0` | 宿主机绑定地址 |
| `MCP_PORT` | `8765` | 宿主机端口 |

容器内固定：`JDAPIS_AUTH_FILE=/tmp/jdapis/auth.json`，且 `/tmp/jdapis` 为 **tmpfs**（无 volumes / 无 named volume）。

### Cursor 连接（SSE）

本机：

```json
{
  "mcpServers": {
    "jd-apis": {
      "url": "http://127.0.0.1:8765/sse"
    }
  }
}
```

外网服务器（安全组放行 TCP 8765 后）：

```json
{
  "mcpServers": {
    "jd-apis": {
      "url": "http://你的公网IP:8765/sse"
    }
  }
}
```

先 `compose up`，再在 Cursor 中启用/刷新该 server。登录在容器内完成；`down` 后登录态丢失。

### 容器内登录（MCP tools）
登录**必须在容器内**完成，通过 Cursor 调用下列 tools（不要把 Cookie 拷到宿主机）：

**扫码（推荐）**

1. `jd_login_qr_start` → 得到 `qr_png_base64` / `qr_data_url`
2. 把二维码展示给用户，用京东 App 扫码并确认
3. `jd_login_qr_wait`（`timeout` 建议 60–180）→ 成功后登录态写入容器临时文件
4. `jd_check_session` 确认账号 pin

若 wait 返回 `status=qr_refreshed`，请扫新码后再 `jd_login_qr_wait`。

**短信**

1. `jd_login_sms_start(mobile="1xxxxxxxxxx")` → 发短信（可能含人机验证，稍慢）
2. `jd_login_sms_submit(sms_code="123456")`
3. 若返回 `need_safe_verify=true`，再 `jd_login_sms_safe_submit(safe_code="......")`

**登出 / 查存储位置**

- `jd_logout`：清除容器内临时登录态
- `jd_auth_storage`：查看 `auth_file` 路径（应为 `/tmp/jdapis/auth.json`）

### 如何确认登录态未落到宿主机

1. `docker compose ... config` / 打开 `docker-compose.yml`：应**没有** `AUTH_FILE`、没有把宿主机路径挂到 auth。
2. 调用 `jd_auth_storage`，路径为容器内 `/tmp/jdapis/auth.json`。
3. 宿主机上不应出现对应 auth 文件；`docker compose down` 后容器与 tmpfs 消失，需重新登录。
4. 可选：`docker inspect jd-apis-mcp` 查看 Mounts —— 不应有 auth 相关 bind mount；应有 tmpfs `/tmp/jdapis`。

## 本机直接运行（开发用）

1. 安装依赖：

```bash
pip install -r requirements.txt
npm install
pip install -r mcp_server/requirements.txt
```

2. （可选）指定临时 auth 路径，避免写进系统用户目录：

```bash
# Linux / macOS
export JDAPIS_AUTH_FILE=/tmp/jdapis/auth.json
# Windows PowerShell
$env:JDAPIS_AUTH_FILE = "$env:TEMP\jdapis\auth.json"
```

3. 启动：

```bash
python mcp_server/server.py
```

本机开发仍可用根目录 `login_demo.py` / `quick.py`，或同样用 MCP 登录 tools。

## 可用 Tools

### 登录

| Tool | 参数 | 说明 |
| --- | --- | --- |
| `jd_login_qr_start` | 无 | 取扫码二维码（base64） |
| `jd_login_qr_wait` | `timeout?=180` | 等待扫码确认 |
| `jd_login_sms_start` | `mobile`, `area_code?` | 发短信验证码 |
| `jd_login_sms_submit` | `sms_code` | 提交短信码 |
| `jd_login_sms_safe_submit` | `safe_code` | 额外安全验证码 |
| `jd_logout` | 无 | 清除容器内登录态 |
| `jd_auth_storage` | 无 | 查看 auth 路径 |

### 业务

| Tool | 参数 | 说明 |
| --- | --- | --- |
| `jd_check_session` | 无 | 检查登录态 |
| `jd_diagnose` | 无 | 诊断登录/风控/限流 |
| `jd_search` | `keyword`, `page?=1` | 搜索商品 |
| `jd_product_detail` | `sku` | 商品详情 |
| `jd_product_comments` | `sku`, `count?=5` | 商品评论 |
| `jd_related_search` | `sku`, `num?=6` | 商详相关搜索 |
| `jd_cart_num` | 无 | 购物车数量 |
| `jd_browse_history` | `page?=1`, `page_size?=20` | 浏览历史 |
| `jd_follow_products` | `page?=1`, `page_size?=20` | 关注商品 |
| `jd_order_list` | `page?=1`, `date_range?="1"` | 订单列表 |
| `jd_search_hotwords` | 无 | 搜索热词（可不登录） |
| `jd_search_relwords` | `keyword?`, `num?=10` | 搜索联想词 |
| `jd_equity_info` | `page_context?`, `sku?` | 会员权益 |
| `jd_chat_info` | `vender_id?`, `pid?`, `order_id?` | 咚咚会话信息 |
| `jd_chat_session_log` | `vender_id?`, `count?=20` | 咚咚历史消息 |

> 咚咚 **WebSocket 长连接收发** 未做成 MCP tool。如需实时聊天请继续用根目录 `chat_demo.py`。

## 调用示例（自然语言）

- 「先 jd_login_qr_start，把二维码给我，我扫完再 wait」
- 「用 jd_search 搜索机械键盘」
- 「检查登录态，再看购物车数量」

## 仅构建镜像（可选）

```bash
docker build -f mcp_server/Dockerfile -t jd-apis-mcp .
```

无 compose 时临时跑（仍建议加 tmpfs，且不要 `-v` 挂 auth）：

```bash
docker run --rm -d \
  --name jd-apis-mcp \
  -p 8765:8765 \
  -e JDAPIS_AUTH_FILE=/tmp/jdapis/auth.json \
  --tmpfs /tmp/jdapis:size=32m,mode=1777 \
  jd-apis-mcp
```

## Docker 注意事项

- **不持久化**：compose 无 auth volume；`down` / 重建容器后需重新登录。
- **端口**：默认 `0.0.0.0:8765`；公网注意风险。
- **网络**：容器需能访问京东相关域名；公司代理请自行配置。
- **体积**：镜像含 Node、`static/`（含 JCAP ONNX），首次构建较慢属正常。

## 国内云主机构建加速（腾讯云等）

国内直连 Docker Hub / `deb.debian.org` 常超时或「卡住很久没反应」。Dockerfile 已默认换国内 **apt / pip / npm** 源；**基础镜像**仍用官方 `node` / `python`，需在宿主机配 Docker Hub 镜像加速。

### 1. 宿主机配置 Docker Hub 镜像（registry-mirrors）

编辑 `/etc/docker/daemon.json`（没有就新建），例如：

```json
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

腾讯云 CVM 内网常用 `mirror.ccs.tencentyun.com`；也可换成你账号控制台提供的加速地址，或其他可用 mirror。然后：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

验证：`docker info` 里应能看到 `Registry Mirrors`。

> 不要随意把 Dockerfile 的 `FROM` 改成不明来源的「替代 base」；优先用官方镜像 + 宿主机 mirror。

### 2. 镜像内 apt / pip / npm（已默认国内源）

| 用途 | 默认 | 覆盖方式 |
| --- | --- | --- |
| apt（Debian bookworm） | `mirrors.cloud.tencent.com` | `--build-arg APT_MIRROR=...` |
| pip | 腾讯云 `mirrors.cloud.tencent.com/pypi/simple` | `--build-arg PIP_INDEX_URL=...` / `PIP_TRUSTED_HOST=...` |
| npm | `registry.npmmirror.com` | `--build-arg NPM_REGISTRY=...` |

若 pip 报 `Could not find a version ... (from versions: none)`，通常是索引不可达/SSL，不是真没有包。可换阿里云：

```bash
docker compose build --progress=plain \
  --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
  --build-arg PIP_TRUSTED_HOST=mirrors.aliyun.com
```

阿里云 apt 示例：`--build-arg APT_MIRROR=mirrors.aliyun.com`  
海外恢复官方源示例：

```bash
docker build -f mcp_server/Dockerfile \
  --build-arg APT_MIRROR=deb.debian.org \
  --build-arg PIP_INDEX_URL=https://pypi.org/simple \
  --build-arg PIP_TRUSTED_HOST=pypi.org \
  --build-arg NPM_REGISTRY=https://registry.npmjs.org \
  -t jd-apis-mcp .
```

也可在 `docker-compose.yml` 的 `build.args` 里覆盖（文件内有注释示例）。npm 默认 npmmirror，一般可用；偶发超时可在 Dockerfile 的 `npm ci` 上加大 `--fetch-timeout` / `--fetch-retries`。

### 3. 看清构建进度（不要干等）

```bash
# 在 mcp_server/ 目录
docker compose build --progress=plain --no-cache

# 或仓库根
docker compose -f mcp_server/docker-compose.yml build --progress=plain
```

`apt-get update` 第一次可能要几十秒；若超过数分钟仍无新输出，再 Ctrl+C，确认已拉取含国内源的 Dockerfile 后重试。

### 4. 拉取本仓库最新 Dockerfile 后重建

```bash
cd /path/to/JdApis
git pull
cd mcp_server
docker compose build --progress=plain
docker compose up -d
```

## 与原项目的关系

```text
mcp_server/          ← 本目录（新增，独立维护）
  bridge.py          ← import JdAPI / init，薄封装
  login_flow.py      ← 扫码/短信分步登录（容器内临时态）
  server.py          ← FastMCP + SSE
  requirements.txt
  Dockerfile
  docker-compose.yml
  README.md

.dockerignore        ← 仓库根（仅影响 docker build）
jd_apis/ utils/ ...  ← 原项目，尽量不改
```

- 通过 `import` 调用现有模块，不复制业务逻辑。
- 不改动根 `package.json`；MCP 依赖单独写在 `mcp_server/requirements.txt`。
- 目录名使用 `mcp_server` 而非 `mcp`，避免与官方 Python 包 `mcp` 命名冲突。

## 合规提醒

本能力仅用于学习、研究和合法的个人自动化。请遵守京东平台规则，控制请求频率，不要提交或传播 Cookie、手机号、验证码等隐私数据。
