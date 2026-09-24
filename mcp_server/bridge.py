# coding: utf-8
"""薄封装：对接现有 JdApis 能力，供 MCP tools 调用。

不修改 jd_apis / utils / builder；仅通过 import 复用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# 保证从 mcp_server/ 启动时也能 import 项目根模块
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from jd_apis.jd_api import JdAPI  # noqa: E402
from utils.common_util import init  # noqa: E402


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def load_auth():
    """加载本地登录态（系统用户目录 auth.json / .env）。"""
    auth, _ = init()
    return auth


def require_login(auth=None):
    """返回 (auth, error_message)。已登录时 error_message 为 None。"""
    auth = auth or load_auth()
    alive, info = JdAPI.check_session(auth)
    if not alive:
        return auth, (
            f"登录态无效：{info}。"
            "请先调用 MCP 登录工具：jd_login_qr_start + jd_login_qr_wait"
            "，或 jd_login_sms_start + jd_login_sms_submit。"
        )
    return auth, None


def check_session() -> str:
    auth = load_auth()
    alive, info = JdAPI.check_session(auth)
    return _json({"alive": alive, "account_or_message": info})


def diagnose() -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    verdict, detail = JdAPI.diagnose(auth)
    return _json({"verdict": verdict, "detail": detail})


def search_wares(keyword: str, page: int = 1) -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    total, wares = JdAPI.search_wares(auth, keyword, page=page)
    return _json({"ok": True, "keyword": keyword, "page": page, "total": total, "wares": wares})


def get_product_detail(sku: str) -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_product_detail(auth, str(sku)))


def get_product_comments(sku: str, count: int = 5) -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_product_comments(auth, str(sku), count=count))


def get_related_search(sku: str, num: int = 6) -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_related_search(auth, str(sku), num=num))


def get_cart_num() -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_cart_num(auth))


def get_browse_history(page: int = 1, page_size: int = 20) -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_browse_history(auth, page=page, page_size=page_size))


def get_follow_products(page: int = 1, page_size: int = 20) -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_follow_products(auth, page=page, page_size=page_size))


def get_order_list(page: int = 1, date_range: str = "1") -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_order_list(auth, page=page, date_range=date_range))


def get_search_hotwords() -> str:
    auth = load_auth()
    return _json(JdAPI.get_search_hotwords(auth))


def get_search_relwords(keyword: str = "", num: int = 10) -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_search_relwords(auth, keyword=keyword, num=num))


def get_equity_info(page_context: str = "search", sku: str = "") -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_equity_info(auth, page_context=page_context, sku=sku))


def get_chat_info(vender_id: str = "1", pid: str = "", order_id: str = "") -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_chat_info(auth, vender_id=vender_id, pid=pid, order_id=order_id))


def get_chat_session_log(vender_id: str = "1", count: int = 20) -> str:
    auth, err = require_login()
    if err:
        return _json({"ok": False, "error": err})
    return _json(JdAPI.get_chat_session_log(auth, vender_id=vender_id, count=count))
