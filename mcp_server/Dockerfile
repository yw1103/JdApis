# JdApis MCP SSE — 构建上下文须为仓库根目录：
#   docker build -f mcp_server/Dockerfile -t jd-apis-mcp .
#
# 镜像含 Python（JdApis）+ Node（h5st / 设备票据等），不改业务核心代码。
# 登录态默认写 /tmp/jdapis/auth.json；compose 用 tmpfs 挂载该目录，不持久化。
#
# 国内云主机（腾讯云等）构建提示：
# - 基础镜像仍走官方 node/python（Docker Hub）。若拉基础镜像超时，请在宿主机
#   /etc/docker/daemon.json 配置 registry-mirrors，见 mcp_server/README.md。
# - apt / pip / npm 默认用国内源（腾讯云 apt+pip、npmmirror）；可用 build-arg 覆盖。
# - pip 若报 “from versions: none”，多为索引不可达/SSL，不是真没有包；可换：
#     --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
#     --build-arg PIP_TRUSTED_HOST=mirrors.aliyun.com
#
# 可选覆盖示例（海外环境可改回官方源）：
#   docker build -f mcp_server/Dockerfile \
#     --build-arg APT_MIRROR=deb.debian.org \
#     --build-arg PIP_INDEX_URL=https://pypi.org/simple \
#     --build-arg PIP_TRUSTED_HOST=pypi.org \
#     --build-arg NPM_REGISTRY=https://registry.npmjs.org \
#     -t jd-apis-mcp .

FROM node:20-bookworm-slim AS node_base

FROM python:3.11-slim-bookworm

# 国内友好默认源；海外或自定义镜像站可通过 --build-arg 覆盖
ARG APT_MIRROR=mirrors.cloud.tencent.com
ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
ARG PIP_TRUSTED_HOST=mirrors.cloud.tencent.com
ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY --from=node_base /usr/local/bin/node /usr/local/bin/node
COPY --from=node_base /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# opencv / onnxruntime / @napi-rs/canvas 运行期库
# 先换 Debian bookworm 源再 apt-get update，避免国内直连 deb.debian.org 卡住
RUN set -eux; \
    if [ -n "${APT_MIRROR}" ] && [ "${APT_MIRROR}" != "deb.debian.org" ]; then \
      sed -i \
        -e "s|deb.debian.org|${APT_MIRROR}|g" \
        -e "s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources 2>/dev/null \
      || sed -i \
        -e "s|deb.debian.org|${APT_MIRROR}|g" \
        -e "s|security.debian.org|${APT_MIRROR}|g" \
        /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libatomic1 \
        libgomp1 \
        libglib2.0-0 \
        fontconfig; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST} \
    NPM_CONFIG_REGISTRY=${NPM_REGISTRY}

# 依赖层缓存：先装 Python / Node，再拷业务代码
COPY requirements.txt ./
COPY mcp_server/requirements.txt ./mcp_server/requirements.txt
COPY package.json package-lock.json ./

# PIP_INDEX_URL / PIP_TRUSTED_HOST 已由 ENV 注入；失败时见文件头阿里云示例。
# npm 默认 npmmirror；若偶发超时可加大超时并重试，例如：
#   npm ci --omit=dev --fetch-timeout=120000 --fetch-retries=5
RUN pip install --no-cache-dir -r requirements.txt -r mcp_server/requirements.txt \
    && npm ci --omit=dev --fetch-retries=3 --fetch-timeout=60000 \
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
