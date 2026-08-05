---
name: backend--troubleshooting
description: Start and troubleshoot the Codly Backend locally with proper logging, health checks, and common issue resolution.
tags: [backend, django, celery, websocket, local-dev, troubleshooting]
---

# Skill: Backend Startup & Troubleshooting

## Purpose
Provide a structured approach to start the Codly Backend (Django + Celery + WebSocket) locally with proper logging, health checks, and systematic troubleshooting for common issues.

---

## Quick Start (TL;DR)

```bash
cd /home/user3/Codly-Clone-Codes/Codly_Backend

# Terminal 1: WebSocket-enabled backend (gunicorn with uvicorn)
source .venv/bin/activate
nohup uv run gunicorn -k uvicorn.workers.UvicornWorker \
  Codly_AI_Langraph.asgi:application \
  --bind 0.0.0.0:8093 \
  --workers 1 \
  --timeout 0 > /tmp/backend.log 2>&1 &

# Terminal 2: Celery worker
source .venv/bin/activate
nohup uv run python -m celery -A Codly_AI_Langraph \
  worker --loglevel=info > /tmp/celery.log 2>&1 &

# Wait 20-30 seconds for startup...
sleep 30

# Terminal 3: Check logs
tail -f /tmp/backend.log &
tail -f /tmp/celery.log &

# Test health endpoints (Terminal 4)
curl http://localhost:8093/admin-api/runbooks/
```

---

## Startup Modes

### Mode 1: WebSocket Support (Production/Full Features)
Use this when you need WebSocket live event streaming for runbooks.

```bash
cd /home/user3/Codly-Clone-Codes/Codly_Backend
source .venv/bin/activate

# Start with gunicorn + uvicorn workers
nohup uv run gunicorn \
  -k uvicorn.workers.UvicornWorker \
  Codly_AI_Langraph.asgi:application \
  --bind 0.0.0.0:8093 \
  --workers 1 \
  --timeout 0 \
  > /tmp/backend.log 2>&1 &

echo $!  # Save PID for later if needed
```

**Why gunicorn + uvicorn?**
- Gunicorn manages process lifecycle
- Uvicorn workers handle ASGI (async, WebSocket)
- `--workers 1` keeps single process (simpler for local dev)
- `--timeout 0` disables timeout (important for long-running tasks)

### Mode 2: Development (No WebSocket)
Use this for faster iteration when not testing WebSocket features.

```bash
cd /home/user3/Codly-Clone-Codes/Codly_Backend
source .venv/bin/activate

nohup uv run python manage.py runserver 0.0.0.0:8093 \
  > /tmp/backend.log 2>&1 &
```

**Trade-off:**
- ✅ Faster startup, auto-reload
- ❌ No WebSocket support (runbook live events won't stream)

---

## Celery Worker Startup

Run in separate terminal:

```bash
cd /home/user3/Codly-Clone-Codes/Codly_Backend
source .venv/bin/activate

nohup uv run python -m celery \
  -A Codly_AI_Langraph \
  worker \
  --loglevel=info \
  > /tmp/celery.log 2>&1 &

echo $!  # Save PID
```

**What to expect:**
```
[tasks]
  . chatbot.tasks.sample_task
  . runbooks.tasks.execute_runbook_task
  . runbooks.tasks.resume_runbook_task
  . [... more tasks ...]

[2026-04-26 13:45:02,123: INFO/MainProcess] celery@hostname ready.
```

---

## ⏳ CRITICAL: Wait 20-30 Seconds Before Testing

**Why?**
- Django loads all models, migrations, settings (8-15 sec)
- Channels/Redis connects (2-5 sec)
- Celery discovers tasks (3-5 sec)
- Full startup: 20-30 seconds

**DO NOT** test endpoints immediately. Wait:

```bash
echo "Waiting 30 seconds for full startup..."
sleep 30
echo "✅ Backend should be ready now"
```

---

## Health Checks

### Check Backend API (REST)

```bash
# Should return 401 Unauthorized (no auth token) — this is normal
curl -v http://localhost:8093/admin-api/runbooks/

# Expected response:
# HTTP/1.1 401 Unauthorized
# {"detail":"Authentication credentials were not provided."}
```

**✅ Pass:** Returns 401  
**❌ Fail:** Connection refused, timeout, 500 error → backend not started

---

### Check Backend Logs

```bash
# Follow in real-time
tail -f /tmp/backend.log

# Show last 50 lines
tail -n 50 /tmp/backend.log

# Search for errors
grep -i "error\|exception" /tmp/backend.log
```

**✅ Healthy signs:**
```
[2026-04-26 13:45:12] Starting development server
[2026-04-26 13:45:15] Quit the server with CONTROL-C
[2026-04-26 13:45:18] GET /admin-api/runbooks/ HTTP/1.1" 401
```

**❌ Problem signs:**
```
ImportError: No module named 'runbooks'
ModuleNotFoundError: No module named 'Codly_AI_Langraph'
psycopg2.OperationalError: could not connect to server
```

---

### Check Celery Worker

```bash
# Follow Celery logs
tail -f /tmp/celery.log

# Check for successful task registration
grep "celery@" /tmp/celery.log | head -20

# Watch for task execution
grep "Received task\|Task.*succeeded" /tmp/celery.log | tail -10
```

**✅ Healthy signs:**
```
[2026-04-26 13:45:18,456: INFO/MainProcess] celery@hostname ready.
[2026-04-26 13:45:20,123: INFO/MainProcess] Received task: runbooks.tasks.execute_runbook_task
[2026-04-26 13:45:25,789: INFO/ForkPoolWorker-1] Task runbooks.tasks.execute_runbook_task succeeded
```

**❌ Problem signs:**
```
ERROR: Unexpected token (syntax error in task code)
ERROR: No broker available
ERROR: Connection refused connecting to Redis
```

---

### Check WebSocket (Gunicorn Only)

Test WebSocket connectivity (only works with gunicorn mode):

```bash
# Use websocat CLI tool (if installed)
websocat ws://localhost:8093/ws/runbooks/run/test-run-id/

# Or use Python
python3 << 'EOF'
import asyncio
import websockets

async def test_ws():
    try:
        async with websockets.connect('ws://localhost:8093/ws/runbooks/run/test/') as ws:
            print("✅ WebSocket connected!")
            msg = await ws.recv()
            print(f"Received: {msg}")
    except Exception as e:
        print(f"❌ WebSocket failed: {e}")

asyncio.run(test_ws())
EOF
```

**✅ Success:** Shows "WebSocket connected"  
**❌ Failure:** "Connection refused", "404", or timeout

---

## Common Issues & Fixes

### Issue 1: Port 8093 Already in Use

```bash
# Find what's using port 8093
lsof -i :8093

# Or with netstat
netstat -tlnp | grep 8093

# Kill the old process
kill -9 <PID>

# Or change port (edit settings, restart)
```

---

### Issue 2: Redis Connection Failed

**Error message:**
```
ConnectionError: Error 111 connecting to 127.0.0.1:6379
```

**Fix:**
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# If not running, start Redis
redis-server --port 6379 &

# Verify again
redis-cli ping
```

---

### Issue 3: ModuleNotFoundError (missing app registration)

**Error:**
```
ModuleNotFoundError: No module named 'runbooks'
```

**Fix:**
```bash
# Verify app is in INSTALLED_APPS
grep -n "runbooks.apps" Codly_AI_Langraph/settings.py

# If missing, add to settings.py:
# INSTALLED_APPS = [
#     ...
#     'runbooks.apps.RunbooksConfig',
# ]

# Run migrations to register
python manage.py migrate runbooks
```

---

### Issue 4: Celery Tasks Not Running

**Symptoms:**
- Celery worker starts but shows no tasks
- Backend creates runbook runs but they never execute

**Debug steps:**
```bash
# 1. Confirm Celery received the task
grep "Received task" /tmp/celery.log

# 2. Check task result in DB
python manage.py shell
>>> from runbooks.models import RunBookRun
>>> run = RunBookRun.objects.latest('created_at')
>>> print(run.status, run.id)

# 3. Restart Celery (it may have missed task registration)
pkill -f "celery.*worker"
sleep 2
# Re-run Celery startup command from above
```

---

### Issue 5: WebSocket Connection Fails

**Error in browser:**
```
WebSocket connection to 'ws://localhost:8093/ws/...' failed
```

**Possible causes & fixes:**

| Cause | Fix |
|-------|-----|
| Running in dev mode (runserver) | Switch to gunicorn mode (Mode 1 above) |
| Backend not fully started | Wait 30 seconds, check `/tmp/backend.log` |
| Port wrong in frontend | Verify `buildRunWsUrl()` uses localhost:8093 |
| Redis not running | Check: `redis-cli ping` |
| Channels layer not configured | Verify Redis connection in settings |

---

### Issue 6: Frontend Still Shows "Waiting / Disconnected"

After backend is healthy, if frontend doesn't update:

```bash
# 1. Clear frontend cache
cd /home/user3/Codly-Clone-Codes/codly-admin-portal
rm -rf .next node_modules
bun install

# 2. Rebuild frontend
bun run build  # or bun run dev

# 3. Hard refresh browser (Ctrl+Shift+R on Chrome/Firefox)

# 4. Check browser console for errors
# F12 → Console tab → look for WebSocket errors
```

---

## Troubleshooting Workflow

When something breaks, follow this order:

```
1. Check logs first
   └─ tail -f /tmp/backend.log
   └─ tail -f /tmp/celery.log

2. Verify processes are running
   └─ ps aux | grep gunicorn
   └─ ps aux | grep celery

3. Test API directly (bypass frontend)
   └─ curl http://localhost:8093/admin-api/runbooks/

4. Check port conflicts
   └─ lsof -i :8093

5. Check dependencies (Redis, DB)
   └─ redis-cli ping
   └─ python manage.py dbshell

6. Restart components in order
   └─ Restart backend first
   └─ Wait 30 seconds
   └─ Restart Celery
   └─ Wait 10 seconds
   └─ Test again
```

---

## Log File Reference

| Component | Log Path | Key Search Terms |
|-----------|----------|-------------------|
| Backend | `/tmp/backend.log` | `ERROR`, `exception`, `ModuleNotFoundError`, `ConnectionError` |
| Celery | `/tmp/celery.log` | `Received task`, `succeeded`, `failed`, `ERROR` |
| Combined | `tail -f /tmp/*.log` | Monitor all in one view |

---

## Cleanup & Restart

```bash
# Stop all backend services
pkill -f gunicorn
pkill -f "python manage.py runserver"
pkill -f "celery.*worker"

# Wait for clean shutdown
sleep 3

# Clear old logs
rm /tmp/backend.log /tmp/celery.log

# Restart (follow Quick Start above)
```

---

## Summary Checklist

After starting backend, verify:

- [ ] No port conflicts (`lsof -i :8093`)
- [ ] Backend logs healthy (`tail -n 20 /tmp/backend.log`)
- [ ] API responds (`curl http://localhost:8093/admin-api/runbooks/`)
- [ ] Celery worker ready (`tail -n 20 /tmp/celery.log`)
- [ ] Redis running (`redis-cli ping`)
- [ ] WebSocket ready (gunicorn mode only)
- [ ] Waited at least 30 seconds since startup

Once all pass ✅, frontend should connect and runbooks should execute!

