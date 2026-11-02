"""C.O.R.E. server console — ALB Lambda target behind console.codly.ai.

Routes
    GET  /                               login page, or the console when signed in
    POST /login                          form post, sets the session cookie
    POST /api/logout
    GET  /api/servers                    summary of every server
    GET  /api/servers/<key>              facts + CloudWatch telemetry
    GET  /api/servers/<key>/live         live stats over SSM
    GET  /api/servers/<key>/containers   docker containers over SSM
    GET  /api/servers/<key>/logs         ?source=<id>|container=<name>&lines=&filter=
    POST /api/servers/<key>/power        {"action": "start|stop", "confirm": "<key>"}
    GET  /api/activity                   ?key=<server key>

Only the instance IDs in config.json can ever be touched.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from urllib.parse import parse_qs, unquote_plus

from botocore.exceptions import ClientError

import cloud

SESSION_TTL = int(os.environ.get("SESSION_TTL", "3600"))
COOKIE = "core_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "core-console"
CONTAINER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
LOCKOUT = cloud.CONFIG["lockout"]

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "ui.html")) as _f:
    UI_HTML = _f.read()
with open(os.path.join(_HERE, "login.html")) as _f:
    LOGIN_HTML = _f.read()


# ---------------------------------------------------------------- auth
def _verify_password(password):
    salt_hex, hash_hex = os.environ["PASSWORD_HASH"].split(":")
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                               n=2 ** 14, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
    return hmac.compare_digest(candidate.hex(), hash_hex)


def _sign(payload):
    return hmac.new(os.environ["SESSION_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()


def _new_session():
    payload = f"{int(time.time()) + SESSION_TTL}.{secrets.token_hex(8)}"
    return f"{payload}.{_sign(payload)}"


def _session_valid(headers):
    cookies = dict(part.strip().split("=", 1)
                   for part in headers.get("cookie", "").split(";") if "=" in part)
    try:
        exp, nonce, sig = cookies.get(COOKIE, "").split(".")
    except ValueError:
        return False
    return hmac.compare_digest(sig, _sign(f"{exp}.{nonce}")) and int(exp) > time.time()


def _lock_name(ip):
    return f"lockout/{hashlib.sha256(ip.encode()).hexdigest()[:24]}.json"


def _recent_failures(ip):
    cutoff = time.time() - LOCKOUT["window_seconds"]
    return [t for t in cloud.read_json(_lock_name(ip), {"fails": []})["fails"] if t > cutoff]


def _login(event, ip):
    fails = _recent_failures(ip)
    if len(fails) >= LOCKOUT["max_failures"]:
        wait = int((fails[0] + LOCKOUT["window_seconds"] - time.time()) / 60) + 1
        return _page(429, LOGIN_HTML.replace("{{ERR}}", f"Too many attempts. Try again in {wait} min, sir."))

    password = parse_qs(_body(event)).get("password", [""])[0]
    if _verify_password(password):
        if fails:
            cloud.write_json(_lock_name(ip), {"fails": []})
        cloud.audit("login", ip=ip)
        return _page(302, "", {"Location": "/", "Set-Cookie": _cookie(_new_session(), SESSION_TTL)})

    cloud.write_json(_lock_name(ip), {"fails": fails + [time.time()]})
    cloud.audit("login_failed", ip=ip)
    time.sleep(1.5)
    left = LOCKOUT["max_failures"] - len(fails) - 1
    return _page(401, LOGIN_HTML.replace("{{ERR}}", f"Access denied. {left} attempt(s) left."))


# ---------------------------------------------------------------- HTTP plumbing
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000",
    "Content-Security-Policy": (
        "default-src 'none'; img-src 'self' data:; "
        "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
        "script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
}


def _page(status, body, extra=None, content_type="text/html; charset=utf-8"):
    return {
        "statusCode": status,
        "statusDescription": f"{status} {HTTPStatus(status).phrase}",  # ALB rejects a bare code
        "isBase64Encoded": False,
        "headers": {"Content-Type": content_type, **SECURITY_HEADERS, **(extra or {})},
        "body": body,
    }


def _json(status, payload):
    return _page(status, json.dumps(payload, default=str), content_type="application/json")


def _cookie(value, max_age):
    return f"{COOKIE}={value}; Path=/; Max-Age={max_age}; HttpOnly; Secure; SameSite=Strict"


def _body(event):
    raw = event.get("body") or ""
    return base64.b64decode(raw).decode() if event.get("isBase64Encoded") else raw


def _query(event):
    # ALB passes query values still URL-encoded.
    return {k: unquote_plus(v) for k, v in (event.get("queryStringParameters") or {}).items()}


# ---------------------------------------------------------------- API handlers
def _servers():
    with ThreadPoolExecutor(max_workers=len(cloud.TARGETS)) as pool:
        results = list(pool.map(_safe_summary, cloud.TARGETS.values()))
    return _json(200, results)


def _safe_summary(target):
    try:
        return cloud.summary(target)
    except ClientError as exc:
        return {"key": target["key"], "label": target["label"], "codename": target.get("codename", ""),
                "note": target.get("note", ""), "state": "error",
                "error": exc.response["Error"]["Code"]}


def _detail(target):
    info = cloud.summary(target)
    with ThreadPoolExecutor(max_workers=3) as pool:
        specs = pool.submit(cloud.instance_specs, target, info["type"])
        vols = pool.submit(cloud.volumes, target, info["volume_ids"])
        tele = pool.submit(cloud.telemetry, target)
        info.update(specs=specs.result(), volumes=vols.result(), telemetry=tele.result())
    info["sources"] = target.get("sources", [])
    return _json(200, info)


def _logs(target, q, ip):
    lines = q.get("lines", "200")
    flt = q.get("filter", "all")
    if not lines.isdigit() or not 1 <= int(lines) <= 999 or flt not in ("all", "errors"):
        return _json(400, {"error": "bad lines or filter"})
    source = next((s for s in target.get("sources", []) if s["id"] == q.get("source")), None)
    if source:
        kind, ref = source["kind"], source["ref"]
    elif CONTAINER_RE.match(q.get("container", "")):
        kind, ref = "docker", q["container"]
    else:
        return _json(400, {"error": "unknown log source"})
    cloud.audit("logs", env=target["key"], source=ref, ip=ip)
    return _json(200, cloud.logs(target, kind, ref, lines, flt))


def _power(target, event, ip):
    try:
        req = json.loads(_body(event))
    except ValueError:
        return _json(400, {"error": "bad json"})
    action = req.get("action")
    if action not in ("start", "stop"):
        return _json(400, {"error": "action must be start or stop"})
    if action == "stop" and req.get("confirm") != target["key"]:
        return _json(400, {"error": f"type '{target['key']}' to confirm the shutdown"})
    cloud.power(target, action)
    cloud.audit(action, env=target["key"], instance=target["instance_id"], ip=ip)
    return _json(200, cloud.summary(target))


def _route(method, path, event, headers, ip):
    if path == "/api/servers" and method == "GET":
        return _servers()
    if path == "/api/activity" and method == "GET":
        key = _query(event).get("key")
        return _json(200, cloud.recent_activity(target_key=key if key in cloud.TARGETS else None))

    m = re.fullmatch(r"/api/servers/([a-z0-9-]+)(/[a-z]+)?", path)
    if not m or m.group(1) not in cloud.TARGETS:
        return _json(404, {"error": "not found"})
    target, sub = cloud.TARGETS[m.group(1)], m.group(2) or ""

    if method == "GET" and sub == "":
        return _detail(target)
    if method == "GET" and sub == "/live":
        return _json(200, cloud.live_stats(target))
    if method == "GET" and sub == "/containers":
        return _json(200, cloud.containers(target))
    if method == "GET" and sub == "/logs":
        return _logs(target, _query(event), ip)
    if method == "POST" and sub == "/power":
        return _power(target, event, ip)
    return _json(404, {"error": "not found"})


def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    ip = headers.get("x-forwarded-for", "").split(",")[0].strip()

    if path == "/favicon.ico":
        return _page(204, "")
    if method == "POST" and path == "/login":
        return _login(event, ip)

    authed = _session_valid(headers)
    if method == "GET" and path == "/":
        return _page(200, UI_HTML if authed else LOGIN_HTML.replace("{{ERR}}", ""))
    if not authed:
        return _json(401, {"error": "unauthorized"})
    if method == "POST" and headers.get(CSRF_HEADER) != CSRF_VALUE:
        return _json(403, {"error": "missing csrf header"})
    if method == "POST" and path == "/api/logout":
        return _page(204, "", {"Set-Cookie": _cookie("", 0)})

    try:
        return _route(method, path, event, headers, ip)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        print(json.dumps({"error": code, "path": path, "detail": str(exc)}))
        return _json(502, {"error": code})
