"""AWS access for the server console: EC2 power + facts, CloudWatch telemetry,
SSM Run Command (locked-down document) and S3 storage.

Targets in another account carry a ``role_arn``; every call for them goes
through an assumed-role session. Sessions are cached per warm container.
"""
import datetime as dt
import json
import time
import uuid

import boto3
from botocore.exceptions import ClientError

with open(__file__.rsplit("/", 1)[0] + "/config.json") as _f:
    CONFIG = json.load(_f)

REGION = CONFIG["region"]
TARGETS = {t["key"]: t for t in CONFIG["targets"]}
STORAGE = CONFIG["storage"]

_sessions = {}


# ---------------------------------------------------------------- sessions
def _session(role_arn):
    hit = _sessions.get(role_arn)
    if hit and hit[1] > time.time():
        return hit[0]
    if role_arn:
        c = boto3.client("sts", region_name=REGION).assume_role(
            RoleArn=role_arn, RoleSessionName="server-console", DurationSeconds=3600
        )["Credentials"]
        sess = boto3.Session(
            aws_access_key_id=c["AccessKeyId"],
            aws_secret_access_key=c["SecretAccessKey"],
            aws_session_token=c["SessionToken"],
            region_name=REGION,
        )
    else:
        sess = boto3.Session(region_name=REGION)
    _sessions[role_arn] = (sess, time.time() + 3000)
    return sess


def _client(target, service):
    return _session(target.get("role_arn")).client(service)


# ---------------------------------------------------------------- EC2
def _iso(value):
    return value.isoformat() if isinstance(value, dt.datetime) else value


def summary(target):
    inst = _client(target, "ec2").describe_instances(
        InstanceIds=[target["instance_id"]]
    )["Reservations"][0]["Instances"][0]
    tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
    return {
        "key": target["key"],
        "label": target["label"],
        "codename": target.get("codename", ""),
        "note": target.get("note", ""),
        "danger": bool(target.get("danger")),
        "account": target["account"],
        "instance_id": inst["InstanceId"],
        "name": tags.get("Name", ""),
        "state": inst["State"]["Name"],
        "type": inst["InstanceType"],
        "az": inst["Placement"]["AvailabilityZone"],
        "private_ip": inst.get("PrivateIpAddress"),
        "public_ip": inst.get("PublicIpAddress"),
        "launched": _iso(inst.get("LaunchTime")),
        "platform": inst.get("PlatformDetails", ""),
        "arch": inst.get("Architecture", ""),
        "volume_ids": [m["Ebs"]["VolumeId"] for m in inst.get("BlockDeviceMappings", []) if "Ebs" in m],
        "has_logs": True,
    }


def instance_specs(target, instance_type):
    ec2 = _client(target, "ec2")
    spec = ec2.describe_instance_types(InstanceTypes=[instance_type])["InstanceTypes"][0]
    return {
        "vcpus": spec["VCpuInfo"]["DefaultVCpus"],
        "memory_gib": round(spec["MemoryInfo"]["SizeInMiB"] / 1024, 1),
        "network": spec.get("NetworkInfo", {}).get("NetworkPerformance", ""),
    }


def volumes(target, volume_ids):
    if not volume_ids:
        return []
    vols = _client(target, "ec2").describe_volumes(VolumeIds=volume_ids)["Volumes"]
    return [{"id": v["VolumeId"], "size_gib": v["Size"], "type": v["VolumeType"],
             "iops": v.get("Iops"), "encrypted": v["Encrypted"]} for v in vols]


def power(target, action):
    ec2 = _client(target, "ec2")
    ids = [target["instance_id"]]
    if action == "start":
        ec2.start_instances(InstanceIds=ids)
    else:
        ec2.stop_instances(InstanceIds=ids)


# ---------------------------------------------------------------- CloudWatch
def _agent_dims(cw, instance_id, metric, extra=None):
    """CloudWatch-agent metrics carry extra dimensions; look up the exact set."""
    dims = [{"Name": "InstanceId", "Value": instance_id}] + (extra or [])
    found = cw.list_metrics(Namespace="CWAgent", MetricName=metric, Dimensions=dims)["Metrics"]
    return found[0]["Dimensions"] if found else None


def telemetry(target, hours=6):
    cw = _client(target, "cloudwatch")
    iid = target["instance_id"]
    ec2_dims = [{"Name": "InstanceId", "Value": iid}]
    wanted = [
        ("cpu", "CPU", "%", "AWS/EC2", "CPUUtilization", ec2_dims, "Average"),
        ("net_in", "Network in", "bytes", "AWS/EC2", "NetworkIn", ec2_dims, "Sum"),
        ("net_out", "Network out", "bytes", "AWS/EC2", "NetworkOut", ec2_dims, "Sum"),
    ]
    mem = _agent_dims(cw, iid, "mem_used_percent")
    if mem:
        wanted.append(("mem", "Memory", "%", "CWAgent", "mem_used_percent", mem, "Average"))
    disk = _agent_dims(cw, iid, "disk_used_percent", [{"Name": "path", "Value": "/"}])
    if disk:
        wanted.append(("disk", "Disk /", "%", "CWAgent", "disk_used_percent", disk, "Average"))

    end = dt.datetime.now(dt.timezone.utc)
    resp = cw.get_metric_data(
        StartTime=end - dt.timedelta(hours=hours),
        EndTime=end,
        ScanBy="TimestampAscending",
        MetricDataQueries=[{
            "Id": mid,
            "MetricStat": {"Metric": {"Namespace": ns, "MetricName": name, "Dimensions": dims},
                           "Period": 300, "Stat": stat},
        } for mid, _, _, ns, name, dims, stat in wanted],
    )
    by_id = {r["Id"]: r for r in resp["MetricDataResults"]}
    return [{
        "id": mid, "label": label, "unit": unit,
        "points": [[int(ts.timestamp()), round(v, 2)]
                   for ts, v in zip(by_id[mid]["Timestamps"], by_id[mid]["Values"])],
    } for mid, label, unit, *_ in wanted]


# ---------------------------------------------------------------- SSM
def run(target, action, ref="-", lines="200", flt="all", wait_seconds=22):
    """Run the locked-down console document and return (status, stdout)."""
    ssm = _client(target, "ssm")
    cmd = ssm.send_command(
        InstanceIds=[target["instance_id"]],
        DocumentName=CONFIG["ssm_document"],
        Parameters={"action": [action], "target": [ref], "lines": [str(lines)], "filter": [flt]},
        TimeoutSeconds=30,
        Comment=f"server-console {action}",
    )["Command"]["CommandId"]
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        time.sleep(1)
        try:
            inv = ssm.get_command_invocation(CommandId=cmd, InstanceId=target["instance_id"])
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "InvocationDoesNotExist":
                continue
            raise
        if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
            out = inv.get("StandardOutputContent", "")
            if inv["Status"] != "Success" and not out:
                out = inv.get("StandardErrorContent", "") or inv.get("StatusDetails", "")
            return inv["Status"], out
    return "TimedOut", "The server did not answer in time. Is the SSM agent running?"


def _sections(text):
    out, current = {}, None
    for line in text.splitlines():
        if line.startswith("@@"):
            current = line[2:].strip()
            out[current] = []
        elif current:
            out[current].append(line)
    return out


def _json_lines(lines):
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


def live_stats(target):
    status, text = run(target, "stats")
    if status != "Success":
        return {"ok": False, "error": text.strip()[:500]}
    s = _sections(text)

    def nums(name):
        return [int(x) for x in (s.get(name) or ["0 0 0"])[0].split()]

    load = (s.get("load") or ["0 0 0"])[0].split()
    mem_total, mem_used, mem_avail = nums("mem")
    disk_total, disk_used, disk_free = nums("disk")
    containers = [{
        "name": r.get("Name"), "cpu": r.get("CPUPerc"), "mem": r.get("MemUsage"),
        "mem_pct": r.get("MemPerc"), "net": r.get("NetIO"), "pids": r.get("PIDs"),
    } for r in _json_lines(s.get("docker", []))]
    return {
        "ok": True,
        "load": [float(x) for x in load[:3]],
        "cpus": int((s.get("cpus") or ["1"])[0]),
        "boot": (s.get("boot") or [""])[0],
        "os": (s.get("os") or [""])[0],
        "mem": {"total": mem_total, "used": mem_used, "available": mem_avail},
        "disk": {"total": disk_total, "used": disk_used, "free": disk_free},
        "containers": sorted(containers, key=lambda c: c["name"] or ""),
    }


def containers(target):
    status, text = run(target, "containers")
    if status != "Success":
        return []
    return sorted(({"name": r.get("Names"), "state": r.get("State"), "status": r.get("Status"),
                    "image": r.get("Image")} for r in _json_lines(text.splitlines())),
                  key=lambda c: c["name"] or "")


def logs(target, kind, ref, lines, flt):
    action = "file_log" if kind == "file" else "docker_logs"
    status, text = run(target, action, ref, lines, flt)
    return {"ok": status == "Success", "status": status, "text": text}


# ---------------------------------------------------------------- S3 storage
def _s3():
    return _session(STORAGE.get("role_arn")).client("s3")


def _key(*parts):
    return "/".join([STORAGE["prefix"], *parts])


def audit(event, **fields):
    now = dt.datetime.now(dt.timezone.utc)
    record = {"ts": now.isoformat(timespec="seconds"), "event": event, **fields}
    key = _key("audit", now.strftime("%Y/%m/%d"), f"{now.strftime('%H%M%S')}-{uuid.uuid4().hex[:8]}.json")
    try:
        _s3().put_object(Bucket=STORAGE["bucket"], Key=key, Body=json.dumps(record).encode(),
                         ContentType="application/json")
    except ClientError as exc:
        print(json.dumps({"audit_write_failed": str(exc), **record}))
    print(json.dumps({"audit": record}))


def recent_activity(days=3, limit=40, target_key=None):
    s3 = _s3()
    today = dt.datetime.now(dt.timezone.utc)
    keys = []
    for d in range(days):
        prefix = _key("audit", (today - dt.timedelta(days=d)).strftime("%Y/%m/%d")) + "/"
        pages = s3.get_paginator("list_objects_v2").paginate(Bucket=STORAGE["bucket"], Prefix=prefix)
        keys += [o["Key"] for p in pages for o in p.get("Contents", [])]
    out = []
    for key in sorted(keys, reverse=True):
        rec = json.loads(s3.get_object(Bucket=STORAGE["bucket"], Key=key)["Body"].read())
        if target_key is None or rec.get("env") == target_key:
            out.append(rec)
        if len(out) >= limit:
            break
    return out


def read_json(name, default):
    try:
        body = _s3().get_object(Bucket=STORAGE["bucket"], Key=_key(name))["Body"].read()
        return json.loads(body)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return default
        raise


def write_json(name, value):
    _s3().put_object(Bucket=STORAGE["bucket"], Key=_key(name), Body=json.dumps(value).encode(),
                     ContentType="application/json")
