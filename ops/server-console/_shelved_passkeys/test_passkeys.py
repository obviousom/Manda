"""End-to-end passkey flow against a software authenticator (no AWS, no browser).

soft_webauthn only sets the user-present flag, so we derive a variant that also
sets user-verified (what a fingerprint / face prompt produces). The original is
kept to prove that presence-only authenticators are rejected.
"""
import base64
import hashlib
import inspect
import json
import os
import sys

import soft_webauthn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

PW = "dummy-pass-42"
salt = bytes.fromhex("00112233445566778899aabbccddeeff")
digest = hashlib.scrypt(PW.encode(), salt=salt, n=2 ** 14, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
os.environ["PASSWORD_HASH"] = f"{salt.hex()}:{digest.hex()}"
os.environ["SESSION_SECRET"] = "test-secret"

import cloud  # noqa: E402
import lambda_function as lf  # noqa: E402

STORE, AUDIT = {}, []
cloud.read_json = lambda name, default: STORE.get(name, default)
cloud.write_json = lambda name, value: STORE.__setitem__(name, value)
cloud.list_json = lambda prefix: [v for k, v in STORE.items() if k.startswith(prefix)]
cloud.audit = lambda event, **f: AUDIT.append((event, f))
lf.time.sleep = lambda s: None

ORIGIN = "https://console.codly.ai"
_src = inspect.getsource(soft_webauthn).replace("flags = b'\\x41'", "flags = b'\\x45'").replace("flags = b'\\x01'", "flags = b'\\x05'")
_ns = {}
exec(compile(_src, "soft_webauthn_uv", "exec"), _ns)
VerifyingDevice = _ns["SoftWebauthnDevice"]


def b64u(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def unb64u(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def call(method, path, cookies=None, body="", csrf=False, ip="1.2.3.4"):
    headers = {"x-forwarded-for": ip}
    if cookies:
        headers["cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    if csrf:
        headers["x-requested-with"] = "core-console"
    return lf.lambda_handler({"httpMethod": method, "path": path, "headers": headers, "body": body,
                              "isBase64Encoded": False, "queryStringParameters": {}}, None)


def set_cookie(resp):
    name, value = resp["headers"]["Set-Cookie"].split(";")[0].split("=", 1)
    return {name: value}


def enroll(device, session, name):
    r = call("POST", "/api/passkeys/register/options", session, json.dumps({"name": name}), csrf=True)
    assert r["statusCode"] == 200, r
    o = json.loads(r["body"])
    created = device.create({"publicKey": {
        "challenge": unb64u(o["challenge"]), "rp": o["rp"],
        "user": {"id": unb64u(o["user"]["id"]), "name": o["user"]["name"], "displayName": o["user"]["displayName"]},
        "pubKeyCredParams": o["pubKeyCredParams"]}}, ORIGIN)
    cred = {"id": created["id"].decode() if isinstance(created["id"], bytes) else b64u(created["rawId"]),
            "rawId": b64u(created["rawId"]), "type": "public-key", "clientExtensionResults": {},
            "response": {"clientDataJSON": b64u(created["response"]["clientDataJSON"]),
                         "attestationObject": b64u(created["response"]["attestationObject"])}}
    cred["id"] = cred["rawId"]
    return call("POST", "/api/passkeys/register/verify", {**session, **set_cookie(r)},
                json.dumps({"name": name, "credential": cred}), csrf=True)


def unlock(device, origin=ORIGIN, challenge_cookie=None):
    r = call("POST", "/passkey/login/options")
    assert r["statusCode"] == 200, r
    o = json.loads(r["body"])
    got = device.get({"publicKey": {"challenge": unb64u(o["challenge"]), "rpId": o["rpId"]}}, origin)
    cred = {"id": b64u(got["rawId"]), "rawId": b64u(got["rawId"]), "type": "public-key", "clientExtensionResults": {},
            "response": {"clientDataJSON": b64u(got["response"]["clientDataJSON"]),
                         "authenticatorData": b64u(got["response"]["authenticatorData"]),
                         "signature": b64u(got["response"]["signature"]),
                         "userHandle": b64u(got["response"]["userHandle"]) if got["response"].get("userHandle") else None}}
    return call("POST", "/passkey/login/verify", challenge_cookie or set_cookie(r), json.dumps(cred))


# passcode session -> /api/me says "passcode"
r = call("POST", "/login", body=f"password={PW}")
assert r["statusCode"] == 302
session = set_cookie(r)
assert json.loads(call("GET", "/api/me", session)["body"])["who"] == "passcode"

# enrolment needs a session + csrf, and a sane name
assert call("POST", "/api/passkeys/register/options", None, json.dumps({"name": "x y"}), csrf=True)["statusCode"] == 401
assert call("POST", "/api/passkeys/register/options", session, json.dumps({"name": "x y"}))["statusCode"] == 403
assert call("POST", "/api/passkeys/register/options", session, json.dumps({"name": "<script>"}), csrf=True)["statusCode"] == 400

phone = VerifyingDevice()
r = enroll(phone, session, "Test Phone")
assert r["statusCode"] == 200, r
assert len([k for k in STORE if k.startswith("passkeys/")]) == 1
listed = json.loads(call("GET", "/api/passkeys", session)["body"])
assert listed[0]["name"] == "Test Phone" and "public_key" not in listed[0]

# unlock with fingerprint -> session carries the device name
r = unlock(phone)
assert r["statusCode"] == 200, r
phone_session = set_cookie(r)
assert json.loads(call("GET", "/api/me", phone_session)["body"])["who"] == "Test Phone"
assert ("login", {"ip": "1.2.3.4", "who": "Test Phone", "method": "passkey"}) in AUDIT
assert STORE[next(k for k in STORE if k.startswith("passkeys/"))]["last_used"]

# a register challenge can't be used to log in; wrong origin and unknown device rejected
reg_opts = call("POST", "/api/passkeys/register/options", session, json.dumps({"name": "Other"}), csrf=True)
assert unlock(phone, challenge_cookie=set_cookie(reg_opts))["statusCode"] == 400
assert unlock(phone, origin="https://evil.example")["statusCode"] == 401
stranger = VerifyingDevice()
stranger.cred_init("console.codly.ai", b"stranger")          # valid key, never enrolled with the server
assert unlock(stranger)["statusCode"] == 401

# presence-only authenticator (no fingerprint/face) can't enrol
plain = soft_webauthn.SoftWebauthnDevice()
assert enroll(plain, session, "No Biometric")["statusCode"] == 400

# revoke -> that phone is locked out immediately
STORE.pop(next(k for k in STORE if k.startswith("lockout/")), None)
cred_id = listed[0]["id"]
assert call("POST", "/api/passkeys/revoke", session, json.dumps({"id": "../../etc"}), csrf=True)["statusCode"] == 404
assert call("POST", "/api/passkeys/revoke", session, json.dumps({"id": cred_id}), csrf=True)["statusCode"] == 200
assert call("GET", "/api/passkeys", session)["body"] == "[]"
assert unlock(phone)["statusCode"] == 401

# installable app endpoints are public and well-formed
assert json.loads(call("GET", "/manifest.webmanifest")["body"] and
                  base64.b64decode(call("GET", "/manifest.webmanifest")["body"]))["short_name"] == "C.O.R.E."
icon = call("GET", "/icon-512.png")
assert icon["isBase64Encoded"] and base64.b64decode(icon["body"])[:4] == b"\x89PNG"
assert isinstance(json.loads(call("GET", "/.well-known/assetlinks.json")["body"]), list)
login = call("GET", "/")["body"]
assert "bioBtn" in login and "{{PASSCODE}}" not in login

print("PASSKEYS OK")
