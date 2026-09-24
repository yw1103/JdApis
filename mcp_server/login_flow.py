# coding: utf-8
"""容器内扫码 / 短信登录编排（MCP 分步 tools）。

登录态只写入 ``JDAPIS_AUTH_FILE``（compose 默认指向 tmpfs 上的临时路径），
不向宿主机挂载。进程内保留多步登录上下文；容器销毁即全部丢失。
"""

from __future__ import annotations

import base64
import os
import threading
import time
from pathlib import Path
from typing import Any

from builder.auth import JdAuth, default_auth_path
from jd_apis.jd_api import JdAPI
from jd_apis.jd_login_api import JdLoginAPI
from jd_apis.jd_sms_login_api import JdSmsLoginAPI, normalize_mobile
from utils import http_client
from utils.jd_cookie import bootstrap

_lock = threading.Lock()
_qr_state: dict[str, Any] = {}
_sms_state: dict[str, Any] = {}


def _auth_path() -> Path:
    return default_auth_path()


def _persist(auth: JdAuth) -> str:
    path = auth.save(_auth_path())
    return path


def _clear_auth_file() -> bool:
    path = _auth_path()
    if path.is_file():
        path.unlink()
        return True
    return False


def auth_storage_info() -> dict:
    path = _auth_path()
    env = os.getenv("JDAPIS_AUTH_FILE") or ""
    return {
        "auth_file": str(path),
        "exists": path.is_file(),
        "jdapis_auth_file_env": env,
        "note": (
            "登录态仅在容器内该路径；compose 使用 tmpfs 时随容器销毁而丢失，"
            "不会写入宿主机磁盘。"
        ),
    }


def logout() -> dict:
    with _lock:
        _qr_state.clear()
        _sms_state.clear()
    removed = _clear_auth_file()
    return {
        "ok": True,
        "auth_file_removed": removed,
        "storage": auth_storage_info(),
    }


# ---------- 扫码登录 ----------


def qr_start(size: int = 147) -> dict:
    """取一张扫码二维码，返回 base64 PNG；随后调用 ``qr_wait`` 等待确认。"""
    auth = bootstrap(JdAuth(), site="passport")
    session = http_client.session()
    try:
        trace_context = JdLoginAPI._prepare_trace_context(auth, session)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    ok, msg, png = JdLoginAPI.get_qrcode(auth, session, size=size)
    if not ok or not png:
        return {"ok": False, "error": msg or "取二维码失败"}

    with _lock:
        _qr_state.clear()
        _qr_state.update({
            "auth": auth,
            "session": session,
            "trace_context": trace_context,
            "next_refresh": time.time() + JdLoginAPI.QR_REFRESH,
            "last_code": None,
        })

    b64 = base64.b64encode(png).decode("ascii")
    return {
        "ok": True,
        "message": "请用京东 App 扫码并确认，然后调用 jd_login_qr_wait。",
        "qr_png_base64": b64,
        "qr_data_url": f"data:image/png;base64,{b64}",
        "expires_in_sec_approx": JdLoginAPI.QR_REFRESH,
        "next_step": "jd_login_qr_wait",
        "storage": auth_storage_info(),
    }


def qr_wait(timeout: int = 180) -> dict:
    """轮询扫码状态直至成功、超时或无进行中的会话。过期会自动换码并返回新图。"""
    timeout = max(30, min(int(timeout or 180), 300))
    deadline = time.time() + timeout
    refreshed_qr: str | None = None

    with _lock:
        state = dict(_qr_state)
    if not state.get("auth") or not state.get("session"):
        return {
            "ok": False,
            "error": "没有进行中的扫码会话，请先调用 jd_login_qr_start。",
        }

    auth = state["auth"]
    session = state["session"]
    trace_context = state["trace_context"]
    next_refresh = float(state.get("next_refresh") or 0)
    last_code = state.get("last_code")

    while time.time() < deadline:
        if time.time() >= next_refresh:
            ok, msg, png = JdLoginAPI.get_qrcode(auth, session)
            if not ok or not png:
                return {"ok": False, "error": msg or "刷新二维码失败"}
            next_refresh = time.time() + JdLoginAPI.QR_REFRESH
            last_code = None
            refreshed_qr = base64.b64encode(png).decode("ascii")
            with _lock:
                if _qr_state.get("auth") is auth:
                    _qr_state["next_refresh"] = next_refresh
                    _qr_state["last_code"] = last_code

        time.sleep(JdLoginAPI.POLL_INTERVAL)
        res = JdLoginAPI.check_qrcode(auth, session)
        code = res.get("code")
        if code != last_code:
            last_code = code
            with _lock:
                if _qr_state.get("auth") is auth:
                    _qr_state["last_code"] = last_code

        if code == 200 and res.get("ticket"):
            ok, msg, _ = JdLoginAPI.validate_ticket(
                auth, res["ticket"], session, trace_context=trace_context,
            )
            if not ok:
                return {"ok": False, "error": msg, "check": res}
            path = _persist(auth)
            alive, account = JdAPI.check_session(auth)
            with _lock:
                _qr_state.clear()
            return {
                "ok": True,
                "message": msg,
                "alive": alive,
                "account": account,
                "auth_file": path,
                "storage": auth_storage_info(),
            }

        # 若刚换过码，尽早把新图返回给客户端（避免用户扫过期码）
        if refreshed_qr:
            payload = {
                "ok": False,
                "status": "qr_refreshed",
                "message": "二维码已过期并刷新，请扫新码后再次调用 jd_login_qr_wait。",
                "qr_png_base64": refreshed_qr,
                "qr_data_url": f"data:image/png;base64,{refreshed_qr}",
                "next_step": "jd_login_qr_wait",
            }
            refreshed_qr = None
            return payload

    with _lock:
        if _qr_state.get("auth") is auth:
            _qr_state["next_refresh"] = next_refresh
            _qr_state["last_code"] = last_code
    return {
        "ok": False,
        "error": f"{timeout}s 内未完成扫码。可再次 jd_login_qr_wait，或重新 jd_login_qr_start。",
        "storage": auth_storage_info(),
    }


# ---------- 短信登录 ----------


def sms_start(mobile: str, area_code: str = "0086", captcha_timeout: int = 180) -> dict:
    """初始化短信登录并发送验证码（含可选 JCAP 人机验证）。"""
    mobile = (mobile or "").strip()
    if not mobile:
        return {"ok": False, "error": "mobile 不能为空"}

    try:
        normalized = normalize_mobile(mobile, area_code)
    except Exception as exc:  # noqa: BLE001 — 透出校验错误给 MCP 客户端
        return {"ok": False, "error": f"手机号无效：{exc}"}

    auth = bootstrap(JdAuth(), site="passport")
    try:
        from utils.jcap_solver import solve_graphic_captcha

        context = JdSmsLoginAPI.start(auth)
        verify_token = ""
        if context.captcha_status == 1:
            verify_token = solve_graphic_captcha(
                context.captcha_session_id,
                normalized,
                context.auth.cookie_str,
                timeout=max(60, min(int(captcha_timeout or 180), 300)),
                page_url=JdLoginAPI.login_page,
                cookie_callback=lambda cookies: context.auth.update_cookies(
                    cookies, persist=True),
                local_storage=context.auth.local_storage_for(JdLoginAPI.login_page),
                storage_callback=lambda values: context.auth.replace_local_storage(
                    JdLoginAPI.login_page, values, persist=True),
            )
        success, message, _ = JdSmsLoginAPI.send_code(
            context, normalized, verify_token
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"短信登录初始化失败：{exc}"}

    if not success:
        return {"ok": False, "error": message}

    with _lock:
        _sms_state.clear()
        _sms_state.update({
            "context": context,
            "mobile": normalized,
            "need_safe": False,
            "safe_page": None,
            "safe_method": None,
        })

    return {
        "ok": True,
        "message": message,
        "next_step": "jd_login_sms_submit",
        "hint": "请输入收到的 6 位短信验证码，调用 jd_login_sms_submit(sms_code=...)",
        "storage": auth_storage_info(),
    }


def sms_submit(sms_code: str) -> dict:
    """提交短信验证码；若需额外安全验证则进入下一步。"""
    code = str(sms_code or "").strip()
    with _lock:
        state = dict(_sms_state)
    context = state.get("context")
    mobile = state.get("mobile")
    if not context or not mobile:
        return {
            "ok": False,
            "error": "没有进行中的短信登录，请先调用 jd_login_sms_start。",
        }

    success, message, payload = JdSmsLoginAPI.submit_code(context, mobile, code)
    if success:
        path = _persist(context.auth)
        alive, account = JdAPI.check_session(context.auth)
        with _lock:
            _sms_state.clear()
        return {
            "ok": True,
            "message": message,
            "alive": alive,
            "account": account,
            "auth_file": path,
            "storage": auth_storage_info(),
        }

    if isinstance(payload, dict) and payload.get("newSafeVerify"):
        try:
            page = JdSmsLoginAPI.load_safe_verify(context, payload)
            safe_ok, safe_message, method, _ = JdSmsLoginAPI.send_safe_mobile_code(
                context, page
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"额外安全验证初始化失败：{exc}"}
        if not safe_ok:
            return {"ok": False, "error": safe_message}
        with _lock:
            if _sms_state.get("context") is context:
                _sms_state["need_safe"] = True
                _sms_state["safe_page"] = page
                _sms_state["safe_method"] = method
        return {
            "ok": False,
            "need_safe_verify": True,
            "message": safe_message,
            "next_step": "jd_login_sms_safe_submit",
            "hint": "请输入额外安全验证短信码，调用 jd_login_sms_safe_submit(safe_code=...)",
        }

    return {"ok": False, "error": message}


def sms_safe_submit(safe_code: str) -> dict:
    """提交额外安全验证短信码。"""
    code = str(safe_code or "").strip()
    with _lock:
        state = dict(_sms_state)
    context = state.get("context")
    page = state.get("safe_page")
    method = state.get("safe_method")
    if not context or not page or not method or not state.get("need_safe"):
        return {
            "ok": False,
            "error": "没有进行中的安全验证，请先完成 jd_login_sms_submit。",
        }

    safe_ok, safe_message, _ = JdSmsLoginAPI.submit_safe_mobile_code(
        context, page, method, code
    )
    if not safe_ok:
        return {"ok": False, "error": safe_message}
    if not context.auth.is_login:
        return {"ok": False, "error": "额外安全验证通过，但未取得 thor/pin"}

    path = _persist(context.auth)
    alive, account = JdAPI.check_session(context.auth)
    with _lock:
        _sms_state.clear()
    return {
        "ok": True,
        "message": "手机号短信登录成功",
        "alive": alive,
        "account": account,
        "auth_file": path,
        "storage": auth_storage_info(),
    }
