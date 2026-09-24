# JdApis MCP SSE — 构建上下文须为仓库根目录：
#   docker build -f mcp_server/Dockerfile -t jd-apis-mcp .
#
# 镜像含 Python（JdApis）+ Node（h5st / 设备票据等），不改业务核心代码。
# 登录态默认写 /tmp/jdapis/auth.json；compose 用 tmpfs 挂载该目录，不持久化。

FROM node:20-bookworm-slim AS node_base

FROM python:3.11-slim-bookworm

COPY --from=node_base /usr/local/bin/node /usr/local/bin/node
COPY --from=node_base /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# opencv / onnxruntime / @napi-rs/canvas 运行期库
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libatomic1 \
        libgomp1 \
        libglib2.0-0 \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖层缓存：先装 Python / Node，再拷业务代码
COPY requirements.txt ./
COPY mcp_server/requirements.txt ./mcp_server/requirements.txt
COPY package.json package-lock.json ./

RUN pip install --no-cache-dir -r requirements.txt -r mcp_server/requirements.txt \
    && npm ci --omit=dev \
    && npm cache clean --force

COPY builder/ ./builder/
COPY jd_apis/ ./jd_apis/
COPY utils/ ./utils/
COPY static/ ./static/
COPY mcp_server/ ./mcp_server/

# h5st token 缓存；登录目录在镜像内预创建（compose 用 tmpfs 覆盖 /tmp/jdapis）
RUN mkdir -p /app/datas /tmp/jdapis \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app /tmp/jdapis

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    JDAPIS_AUTH_FILE=/tmp/jdapis/auth.json

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8765/health || exit 1

USER appuser

# 容器内必须绑 0.0.0.0，否则宿主机端口映射无效
CMD ["python", "mcp_server/server.py", "--host", "0.0.0.0", "--port", "8765"]
