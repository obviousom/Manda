"""Offline tests: AWS is stubbed out, so this only exercises routing, auth and parsing."""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

PW = "dummy-pass-42"
salt = bytes.fromhex("00112233445566778899aabbccddeeff")
digest = hashlib.scrypt(PW.encode(), salt=salt, n=2 ** 14, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
os.environ["PASSWORD_HASH"] = f"{salt.hex()}:{digest.hex()}"
os.environ["SESSION_SECRET"] = "test-secret"

import cloud  # noqa: E402
import lambda_function as lf  # noqa: E402

STORE, CALLS, AUDIT = {}, [], []
cloud.read_json = lambda name, default: STORE.get(name, default)
cloud.write_json = lambda name, value: STORE.__setitem__(name, value)
cloud.audit = lambda event, **f: AUDIT.append((event, f))
cloud.recent_activity = lambda **kw: [{"ts": "2026-10-19T07:00:00+00:00", "event": "start", "env": "dev"}]
cloud.summary = lambda t: {"key": t["key"], "label": t["label"], "state": "running", "type": "m5a.xlarge",
                           "volume_ids": ["vol-1"], "instance_id": t["instance_id"]}
cloud.instance_specs = lambda t, it: {"vcpus": 4, "memory_gib": 16.0}
cloud.volumes = lambda t, ids: [{"id": "vol-1", "size_gib": 100}]
cloud.telemetry = lambda t: [{"id": "cpu", "label": "CPU", "unit": "%", "points": [[1, 2.0]]}]
cloud.power = lambda t, a: CALLS.append(("power", t["key"], a))
cloud.logs = lambda t, kind, ref, lines, flt: (CALLS.append(("logs", t["key"], kind, ref, lines, flt))
                                              or {"ok": True, "status": "Success", "text": "line"})
lf.time.sleep = lambda s: None


def ev(method, path, headers=None, body="", query=None, ip="1.2.3.4"):
    return {"httpMethod": method, "path": path, "body": body, "isBase64Encoded": False,
            "headers": {"x-forwarded-for": ip, **(headers or {})}, "queryStringParameters": query or {}}


def call(*a, **kw):
    return lf.lambda_handler(ev(*a, **kw), None)


# login page + auth
r = call("GET", "/")
assert r["statusCode"] == 200 and "Authenticate" in r["body"] and "{{ERR}}" not in r["body"]
assert call("GET", "/api/servers")["statusCode"] == 401

# lockout after 5 failures for one IP, other IPs unaffected
for i in range(5):
    assert call("POST", "/login", body="password=nope", ip="9.9.9.9")["statusCode"] == 401
assert call("POST", "/login", body=f"password={PW}", ip="9.9.9.9")["statusCode"] == 429
r = call("POST", "/login", body=f"password={PW}")
assert r["statusCode"] == 302, r
C = {"cookie": r["headers"]["Set-Cookie"].split(";")[0]}
X = {**C, "x-requested-with": "core-console"}

# console + servers + detail
assert "C.O.R.E." in call("GET", "/", C)["body"]
servers = json.loads(call("GET", "/api/servers", C)["body"])
assert [s["key"] for s in servers] == ["dev", "staging", "beta-prod", "cloud-in"]
d = json.loads(call("GET", "/api/servers/dev", C)["body"])
assert d["specs"]["vcpus"] == 4 and d["telemetry"][0]["id"] == "cpu" and d["sources"][0]["ref"] == "backend.log"
assert call("GET", "/api/servers/nope", C)["statusCode"] == 404

# power: csrf, confirm, actions
assert call("POST", "/api/servers/dev/power", C, json.dumps({"action": "stop", "confirm": "dev"}))["statusCode"] == 403
assert call("POST", "/api/servers/dev/power", X, json.dumps({"action": "stop"}))["statusCode"] == 400
assert call("POST", "/api/servers/dev/power", X, json.dumps({"action": "reboot"}))["statusCode"] == 400
assert call("POST", "/api/servers/beta-prod/power", X, json.dumps({"action": "stop", "confirm": "dev"}))["statusCode"] == 400
assert call("POST", "/api/servers/dev/power", X, json.dumps({"action": "stop", "confirm": "dev"}))["statusCode"] == 200
assert call("POST", "/api/servers/staging/power", X, json.dumps({"action": "start"}))["statusCode"] == 200
assert ("power", "dev", "stop") in CALLS and ("power", "staging", "start") in CALLS

# logs: presets, containers, URL-encoded query, injection attempts
assert call("GET", "/api/servers/beta-prod/logs", C, query={"source": "prod-celery-1"})["statusCode"] == 200
assert CALLS[-1] == ("logs", "beta-prod", "docker", "codly_backend_prod-celery-workers-1", "200", "all")
assert call("GET", "/api/servers/cloud-in/logs", C, query={"container": "codly_x", "lines": "500", "filter": "errors"})["statusCode"] == 200
assert CALLS[-1][3:] == ("codly_x", "500", "errors")
for bad in ({"container": "x;rm -rf /"}, {"container": "a%20b"}, {"container": "$(id)"},
            {"source": "backend", "lines": "5000"}, {"source": "backend", "lines": "0"},
            {"source": "backend", "filter": "x"}, {}):
    assert call("GET", "/api/servers/dev/logs", C, query=bad)["statusCode"] == 400, bad

# activity
assert json.loads(call("GET", "/api/activity", C, query={"key": "dev"})["body"])[0]["event"] == "start"

# logout needs csrf
assert call("POST", "/api/logout", C)["statusCode"] == 403
assert call("POST", "/api/logout", X)["statusCode"] == 204

# SSM document: valid JSON, patterns reject injection, no stray placeholders
doc = json.load(open(os.path.join(HERE, "..", "infra", "ssm-document.json")))
pat = re.compile(doc["parameters"]["target"]["allowedPattern"])
assert pat.match("codly_backend_prod-celery-workers-1") and pat.match("backend.log")
assert not any(pat.match(s) for s in ("a;b", "a b", "$(id)", "../etc", "a'b", "", "a/b"))
script = "\n".join(doc["mainSteps"][0]["inputs"]["runCommand"])
assert set(re.findall(r"\{\{\s*(\w+)\s*\}\}", script)) == set(doc["parameters"])

# stats parsing against real-shaped output
sample = """@@load
0.28 0.21 0.14 1/400 1234
@@cpus
4
@@boot
2026-10-19 04:16:00
@@mem
16461950976 5368709120 10737418240
@@disk
107374182400 53687091200 53687091200
@@os
Ubuntu 24.04.1 LTS
@@docker
{"CPUPerc":"0.10%","MemPerc":"0.71%","MemUsage":"111.7MiB / 15.33GiB","Name":"codly_frontend_beta","NetIO":"898kB / 10.2MB","PIDs":"7"}
"""
cloud.run = lambda t, action, *a, **k: ("Success", sample)
s = cloud.live_stats(cloud.TARGETS["beta-prod"])
assert s["ok"] and s["cpus"] == 4 and s["load"][0] == 0.28 and s["mem"]["total"] == 16461950976
assert s["containers"][0]["name"] == "codly_frontend_beta" and s["os"].startswith("Ubuntu")

print("ALL OK")
