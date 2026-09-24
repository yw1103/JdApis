# coding: utf-8
"""JdApis MCP Server（SSE transport）。

端点：
  GET  /sse        — 建立 SSE 连接
  POST /messages/  — 接收客户端 JSON-RPC 消息

启动（在项目根目录）：
  python mcp_server/server.py
  python mcp_server/server.py --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许 `python mcp_server/server.py` 时 import 同目录 bridge
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from mcp.server.fastmcp import FastMCP

import bridge
import login_flow


def create_mcp(host: str = "0.0.0.0", port: int = 8765) -> FastMCP:
    mcp = FastMCP(
        "jd-apis",
        instructions=(
            "京东 JdApis MCP：商品搜索、详情、评论、购物车、订单、热词等。"
            "多数工具需要登录态。Docker/compose 部署下请用容器内登录工具："
            "扫码 jd_login_qr_start → jd_login_qr_wait；"
            "短信 jd_login_sms_start → jd_login_sms_submit（必要时 jd_login_sms_safe_submit）。"
            "登录态仅存容器临时路径，容器销毁即丢失。"
            "请遵守京东平台规则，控制请求频率，勿泄露 Cookie、手机号与验证码。"
        ),
        host=host,
        port=port,
        sse_path="/sse",
        message_path="/messages/",
    )

    @mcp.tool(
        name="jd_login_qr_start",
        description=(
            "开始京东 App 扫码登录：返回 PNG 二维码的 base64 / data URL。"
            "拿到后请展示给用户扫码，再调用 jd_login_qr_wait 等待确认。"
        ),
    )
    def jd_login_qr_start() -> str:
        return bridge._json(login_flow.qr_start())

    @mcp.tool(
        name="jd_login_qr_wait",
        description=(
            "等待扫码确认（轮询）。timeout 建议 60–180 秒。"
            "若二维码过期会返回新 qr_png_base64，需重新扫码后再 wait。"
        ),
    )
    def jd_login_qr_wait(timeout: int = 180) -> str:
        return bridge._json(login_flow.qr_wait(timeout=timeout))

    @mcp.tool(
        name="jd_login_sms_start",
        description=(
            "开始手机号短信登录并发送验证码（可能含人机验证，耗时较长）。"
            "成功后调用 jd_login_sms_submit 提交 6 位短信码。"
        ),
    )
    def jd_login_sms_start(mobile: str, area_code: str = "0086") -> str:
        return bridge._json(login_flow.sms_start(mobile, area_code=area_code))

    @mcp.tool(
        name="jd_login_sms_submit",
        description=(
            "提交短信验证码。若返回 need_safe_verify=true，"
            "再调用 jd_login_sms_safe_submit。"
        ),
    )
    def jd_login_sms_submit(sms_code: str) -> str:
        return bridge._json(login_flow.sms_submit(sms_code))

    @mcp.tool(
        name="jd_login_sms_safe_submit",
        description="提交额外安全验证短信码（仅在 sms_submit 提示需要时使用）。",
    )
    def jd_login_sms_safe_submit(safe_code: str) -> str:
        return bridge._json(login_flow.sms_safe_submit(safe_code))

    @mcp.tool(
        name="jd_logout",
        description="清除容器内临时登录态与进行中的登录会话（不写宿主机）。",
    )
    def jd_logout() -> str:
        return bridge._json(login_flow.logout())

    @mcp.tool(
        name="jd_auth_storage",
        description="查看当前登录态文件路径与是否存在（用于确认未挂载到宿主机）。",
    )
    def jd_auth_storage() -> str:
        return bridge._json(login_flow.auth_storage_info())

    @mcp.tool(name="jd_check_session", description="检查京东登录态是否有效，返回账号 pin 或错误信息。")
    def jd_check_session() -> str:
        return bridge.check_session()

    @mcp.tool(name="jd_diagnose", description="诊断登录态 / 风控 / 限流（大面积 403 时使用）。")
    def jd_diagnose() -> str:
        return bridge.diagnose()

    @mcp.tool(name="jd_search", description="按关键词搜索京东商品，返回 total 与精简商品列表。")
    def jd_search(keyword: str, page: int = 1) -> str:
        return bridge.search_wares(keyword, page=page)

    @mcp.tool(name="jd_product_detail", description="获取商品详情（价格、库存、规格、店铺等）。")
    def jd_product_detail(sku: str) -> str:
        return bridge.get_product_detail(sku)

    @mcp.tool(name="jd_product_comments", description="获取商品评论。")
    def jd_product_comments(sku: str, count: int = 5) -> str:
        return bridge.get_product_comments(sku, count=count)

    @mcp.tool(name="jd_related_search", description="获取商详页相关搜索。")
    def jd_related_search(sku: str, num: int = 6) -> str:
        return bridge.get_related_search(sku, num=num)

    @mcp.tool(name="jd_cart_num", description="获取购物车商品数量。")
    def jd_cart_num() -> str:
        return bridge.get_cart_num()

    @mcp.tool(name="jd_browse_history", description="获取浏览历史。")
    def jd_browse_history(page: int = 1, page_size: int = 20) -> str:
        return bridge.get_browse_history(page=page, page_size=page_size)

    @mcp.tool(name="jd_follow_products", description="获取关注的商品列表。")
    def jd_follow_products(page: int = 1, page_size: int = 20) -> str:
        return bridge.get_follow_products(page=page, page_size=page_size)

    @mcp.tool(name="jd_order_list", description="获取订单列表。date_range 与网页订单中心一致，默认近期。")
    def jd_order_list(page: int = 1, date_range: str = "1") -> str:
        return bridge.get_order_list(page=page, date_range=date_range)

    @mcp.tool(name="jd_search_hotwords", description="获取搜索热词（免签名，可不登录）。")
    def jd_search_hotwords() -> str:
        return bridge.get_search_hotwords()

    @mcp.tool(name="jd_search_relwords", description="获取搜索联想/相关词。")
    def jd_search_relwords(keyword: str = "", num: int = 10) -> str:
        return bridge.get_search_relwords(keyword=keyword, num=num)

    @mcp.tool(name="jd_equity_info", description="获取会员权益信息。")
    def jd_equity_info(page_context: str = "search", sku: str = "") -> str:
        return bridge.get_equity_info(page_context=page_context, sku=sku)

    @mcp.tool(name="jd_chat_info", description="获取咚咚客服会话初始化信息（非 WebSocket 长连接）。")
    def jd_chat_info(vender_id: str = "1", pid: str = "", order_id: str = "") -> str:
        return bridge.get_chat_info(vender_id=vender_id, pid=pid, order_id=order_id)

    @mcp.tool(name="jd_chat_session_log", description="获取咚咚会话历史消息日志。")
    def jd_chat_session_log(vender_id: str = "1", count: int = 20) -> str:
        return bridge.get_chat_session_log(vender_id=vender_id, count=count)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok", "server": "jd-apis-mcp", "transport": "sse"})

    return mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JdApis MCP Server (SSE)")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址，默认 0.0.0.0（容器/外网映射需要）")
    parser.add_argument("--port", type=int, default=8765, help="监听端口，默认 8765")
    args = parser.parse_args(argv)

    mcp = create_mcp(host=args.host, port=args.port)
    print(f"[jd-apis-mcp] SSE  listening http://{args.host}:{args.port}/sse")
    print(f"[jd-apis-mcp] messages  http://{args.host}:{args.port}/messages/")
    print(f"[jd-apis-mcp] health    http://{args.host}:{args.port}/health")
    mcp.run(transport="sse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
