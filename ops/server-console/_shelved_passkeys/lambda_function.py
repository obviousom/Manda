"""C.O.R.E. server console — ALB Lambda target behind console.codly.ai.

Routes
    GET  /                                  login page, or the console when signed in
    POST /login                             passcode form post (if ALLOW_PASSCODE=1)
    POST /passkey/login/options             WebAuthn challenge for fingerprint / face unlock
    POST /passkey/login/verify              signed challenge -> session cookie
    GET  /manifest.webmanifest, /icon-*.png installable web app
    GET  /.well-known/assetlinks.json       lets the Android app open this site full screen
    POST /api/logout
    GET  /api/servers                       summary of every server
    GET  /api/servers/<key>                 facts + CloudWatch telemetry
    GET  /api/servers/<key>/live            live stats over SSM
    GET  /api/servers/<key>/containers      docker containers over SSM
    GET  /api/servers/<key>/logs            ?source=<id>|container=<name>&lines=&filter=
    POST /api/servers/<key>/power           {"action": "start|stop", "confirm": "<key>"}
    GET  /api/activity                      ?key=<server key>
    GET  /api/passkeys                      enrolled devices
    POST /api/passkeys/register/options     {"name": "<device name>"}
    POST /api/passkeys/register/verify      {"name": ..., "credential": {...}}
    POST /api/passkeys/revoke               {"id": "<credential id>"}

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
import passkeys

SESSION_TTL = int(os.environ.get("SESSION_TTL", "3600"))
ALLOW_PASSCODE = os.environ.get("ALLOW_PASSCODE", "1") == "1"
COOKIE = "core_session"
CHALLENGE_COOKIE = "core_challenge"
CHALLENGE_TTL = 300
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "core-console"
CONTAINER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
DEVICE_NAME_RE = re.compile(r"^[\w .'()-]{2,40}$")
LOCKOUT = cloud.CONFIG["lockout"]

_HERE = os.path.dirname(os.path.abspath(__file__))


def _read(name, mode="r"):
    with open(os.path.join(_HERE, name), mode) as f:
        return f.read()


UI_HTML = _read("ui.html")
LOGIN_HTML = _read("login.html")
STATIC = {
    "/manifest.webmanifest": ("application/manifest+json", _read("static/manifest.webmanifest", "rb")),
    "/icon-192.png": ("image/png", _read("static/icon-192.png", "rb")),
    "/icon-512.png": ("image/png", _read("static/icon-512.png", "rb")),
    "/icon-maskable-512.png": ("image/png", _read("static/icon-maskable-512.png", "rb")),
}


# ---------------------------------------------------------------- sessions
def _sign(payload):
    return hmac.new(os.environ["SESSION_SECRET"].encode(), payload.encode(), hashlib.sha256).hexdigest()


def _b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode()


def _new_session(who):
    payload = f"{int(time.time()) + SESSION_TTL}.{secrets.token_hex(8)}.{_b64(who)}"
    return f"{payload}.{_sign(payload)}"


def _cookies(headers):
    return dict(part.strip().split("=", 1) for part in headers.get("cookie", "").split(";") if "=" in part)


def _session_who(headers):
    """Name of the signed-in person/device, or None."""
    try:
        exp, nonce, who, sig = _cookies(headers).get(COOKIE, "").split(".")
        if hmac.compare_digest(sig, _sign(f"{exp}.{nonce}.{who}")) and int(exp) > time.time():
            return _unb64(who)
    except ValueError:
        pass
    return None


def _cookie(name, value, max_age):
    return f"{name}={value}; Path=/; Max-Age={max_age}; HttpOnly; Secure; SameSite=Strict"


def _session_cookie(who):
    return _cookie(COOKIE, _new_session(who), SESSION_TTL)


def _challenge_cookie(kind, challenge):
    payload = f"{kind}.{int(time.time()) + CHALLENGE_TTL}.{base64.urlsafe_b64encode(challenge).decode().rstrip('=')}"
    return _cookie(CHALLENGE_COOKIE, f"{payload}.{_sign(payload)}", CHALLENGE_TTL)


def _challenge(headers, kind):
    try:
        got_kind, exp, chal, sig = _cookies(headers).get(CHALLENGE_COOKIE, "").split(".")
    except ValueError:
        return None
    if got_kind != kind or int(exp) < time.time() or not hmac.compare_digest(sig, _sign(f"{got_kind}.{exp}.{chal}")):
        return None
    return base64.urlsafe_b64decode(chal + "=" * (-len(chal) % 4))


# ---------------------------------------------------------------- lockout + passcode
def _verify_password(password):
    salt_hex, hash_hex = os.environ["PASSWORD_HASH"].split(":")
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                               n=2 ** 14, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
    return hmac.compare_digest(candidate.hex(), hash_hex)


def _lock_name(ip):
    return f"lockout/{hashlib.sha256(ip.encode()).hexdigest()[:24]}.json"


def _recent_failures(ip):
    cutoff = time.time() - LOCKOUT["window_seconds"]
    return [t for t in cloud.read_json(_lock_name(ip), {"fails": []})["fails"] if t > cutoff]


def _record_failure(ip, fails, event):
    cloud.write_json(_lock_name(ip), {"fails": fails + [time.time()]})
    cloud.audit(event, ip=ip)
    time.sleep(1.5)
    return LOCKOUT["max_failures"] - len(fails) - 1


def _locked_minutes(fails):
    if len(fails) < LOCKOUT["max_failures"]:
        return 0
    return int((fails[0] + LOCKOUT["window_seconds"] - time.time()) / 60) + 1


def _login_page(status=200, err=""):
    page = LOGIN_HTML.replace("{{ERR}}", err).replace("{{PASSCODE}}", "1" if ALLOW_PASSCODE else "0")
    return _page(status, page)


def _passcode_login(event, ip):
    if not ALLOW_PASSCODE:
        return _login_page(403, "Passcode login is disabled. Use your fingerprint or face, sir.")
    fails = _recent_failures(ip)
    if _locked_minutes(fails):
        return _login_page(429, f"Too many attempts. Try again in {_locked_minutes(fails)} min, sir.")
    if _verify_password(parse_qs(_body(event)).get("password", [""])[0]):
        if fails:
            cloud.write_json(_lock_name(ip), {"fails": []})
        cloud.audit("login", ip=ip, who="passcode")
        return _page(302, "", {"Location": "/", "Set-Cookie": _session_cookie("passcode")})
    left = _record_failure(ip, fails, "login_failed")
    return _login_page(401, f"Access denied. {left} attempt(s) left.")


# ---------------------------------------------------------------- passkey login
def _passkey_login_options():
    options, challenge = passkeys.authentication_options()
    return _page(200, options, {"Set-Cookie": _challenge_cookie("login", challenge)}, "application/json")


def _passkey_login_verify(event, headers, ip):
    fails = _recent_failures(ip)
    if _locked_minutes(fails):
        return _json(429, {"error": f"Too many attempts. Try again in {_locked_minutes(fails)} min."})
    challenge = _challenge(headers, "login")
    if not challenge:
        return _json(400, {"error": "Challenge expired. Try again."})
    try:
        device = passkeys.authenticate(_body(event), challenge)
    except Exception as exc:  # webauthn raises several exception types for a bad assertion
        print(json.dumps({"passkey_login_error": str(exc)[:300]}))
        device = None
    if not device:
        left = _record_failure(ip, fails, "passkey_failed")
        return _json(401, {"error": f"Passkey not recognised. {left} attempt(s) left."})
    cloud.audit("login", ip=ip, who=device["name"], method="passkey")
    return _page(200, json.dumps({"ok": True, "name": device["name"]}),
                 {"Set-Cookie": _session_cookie(device["name"])}, "application/json")


# ---------------------------------------------------------------- HTTP plumbing
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000",
    "Content-Security-Policy": (
        "default-src 'none'; img-src 'self' data:; manifest-src 'self'; "
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


def _static(path):
    content_type, data = STATIC[path]
    resp = _page(200, base64.b64encode(data).decode(), {"Cache-Control": "public, max-age=86400"}, content_type)
    resp["isBase64Encoded"] = True
    return resp


def _assetlinks():
    android = cloud.CONFIG["android"]
    statements = [{
        "relation": ["delegate_permission/common.handle_all_urls",
                     "delegate_permission/common.get_login_creds"],
        "target": {"namespace": "android_app", "package_name": android["package"],
                   "sha256_cert_fingerprints": android["sha256_cert_fingerprints"]},
    }] if android["sha256_cert_fingerprints"] else []
    return _page(200, json.dumps(statements), {"Cache-Control": "public, max-age=3600"}, "application/json")


def _body(event):
    raw = event.get("body") or ""
    return base64.b64decode(raw).decode() if event.get("isBase64Encoded") else raw


def _json_body(event):
    try:
        data = json.loads(_body(event))
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


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


def _logs(target, q, ip, who):
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
    cloud.audit("logs", env=target["key"], source=ref, ip=ip, who=who)
    return _json(200, cloud.logs(target, kind, ref, lines, flt))


def _power(target, event, ip, who):
    req = _json_body(event)
    if req is None:
        return _json(400, {"error": "bad json"})
    action = req.get("action")
    if action not in ("start", "stop"):
        return _json(400, {"error": "action must be start or stop"})
    if action == "stop" and req.get("confirm") != target["key"]:
        return _json(400, {"error": f"type '{target['key']}' to confirm the shutdown"})
    cloud.power(target, action)
    cloud.audit(action, env=target["key"], instance=target["instance_id"], ip=ip, who=who)
    return _json(200, cloud.summary(target))


def _passkey_api(method, path, event, headers, ip, who):
    if path == "/api/passkeys" and method == "GET":
        return _json(200, [{k: c.get(k) for k in ("id", "name", "created", "last_used")}
                           for c in passkeys.all_credentials()])
    req = _json_body(event)
    if req is None:
        return _json(400, {"error": "bad json"})
    if path == "/api/passkeys/register/options":
        name = str(req.get("name", "")).strip()
        if not DEVICE_NAME_RE.match(name):
            return _json(400, {"error": "Device name: 2-40 letters, numbers, spaces"})
        options, challenge = passkeys.registration_options(name)
        return _page(200, options, {"Set-Cookie": _challenge_cookie("register", challenge)}, "application/json")
    if path == "/api/passkeys/register/verify":
        name = str(req.get("name", "")).strip()
        challenge = _challenge(headers, "register")
        if not DEVICE_NAME_RE.match(name) or not challenge or not isinstance(req.get("credential"), dict):
            return _json(400, {"error": "Registration expired or invalid. Try again."})
        try:
            device = passkeys.register(req["credential"], challenge, name)
        except Exception as exc:  # webauthn raises several exception types for a bad attestation
            print(json.dumps({"passkey_register_error": str(exc)[:300]}))
            return _json(400, {"error": "The device's response could not be verified."})
        cloud.audit("passkey_added", device=name, ip=ip, who=who)
        return _json(200, {"ok": True, "id": device["id"], "name": name})
    if path == "/api/passkeys/revoke":
        if not passkeys.revoke(str(req.get("id", ""))):
            return _json(404, {"error": "unknown passkey"})
        cloud.audit("passkey_revoked", device=str(req.get("id", ""))[:16], ip=ip, who=who)
        return _json(200, {"ok": True})
    return _json(404, {"error": "not found"})


def _route(method, path, event, headers, ip, who):
    if path == "/api/me" and method == "GET":
        return _json(200, {"who": who, "passcode_enabled": ALLOW_PASSCODE})
    if path == "/api/servers" and method == "GET":
        return _servers()
    if path == "/api/activity" and method == "GET":
        key = _query(event).get("key")
        return _json(200, cloud.recent_activity(target_key=key if key in cloud.TARGETS else None))
    if path.startswith("/api/passkeys"):
        return _passkey_api(method, path, event, headers, ip, who)

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
        return _logs(target, _query(event), ip, who)
    if method == "POST" and sub == "/power":
        return _power(target, event, ip, who)
    return _json(404, {"error": "not found"})


def lambda_handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    ip = headers.get("x-forwarded-for", "").split(",")[0].strip()

    if path == "/favicon.ico":
        return _static("/icon-192.png")
    if path in STATIC:
        return _static(path)
    if path == "/.well-known/assetlinks.json":
        return _assetlinks()

    try:
        if method == "POST" and path == "/login":
            return _passcode_login(event, ip)
        if method == "POST" and path == "/passkey/login/options":
            return _passkey_login_options()
        if method == "POST" and path == "/passkey/login/verify":
            return _passkey_login_verify(event, headers, ip)

        who = _session_who(headers)
        if method == "GET" and path == "/":
            return _page(200, UI_HTML) if who else _login_page()
        if not who:
            return _json(401, {"error": "unauthorized"})
        if method == "POST" and headers.get(CSRF_HEADER) != CSRF_VALUE:
            return _json(403, {"error": "missing csrf header"})
        if method == "POST" and path == "/api/logout":
            return _page(204, "", {"Set-Cookie": _cookie(COOKIE, "", 0)})
        return _route(method, path, event, headers, ip, who)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        print(json.dumps({"error": code, "path": path, "detail": str(exc)}))
        return _json(502, {"error": code})
