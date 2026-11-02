#!/usr/bin/env bash
# Ships app/ to the existing Lambda behind console.codly.ai and switches it to the console role.
# Keeps the current PASSWORD_HASH / SESSION_SECRET already set on the function.
# To change the passcode:  NEW_PASSCODE='...' bash deploy.sh
set -euo pipefail
cd "$(dirname "$0")"
export AWS_PROFILE=${MAIN_PROFILE:-master} AWS_REGION=ap-south-1 AWS_PAGER=""
FN=codly-server-control
ROLE=arn:aws:iam::603366204162:role/codly-server-console-lambda

python3 tests/test_local.py
mkdir -p build && rm -f build/function.zip
(cd app && python3 -c "import zipfile,glob; z=zipfile.ZipFile('../build/function.zip','w',zipfile.ZIP_DEFLATED); [z.write(f) for f in sorted(glob.glob('*.py')+glob.glob('*.html')+glob.glob('*.json'))]")

aws lambda get-function-configuration --function-name $FN --query Environment.Variables --output json > build/env-current.json
NEW_PASSCODE=${NEW_PASSCODE:-} python3 - <<'EOF'
import hashlib, json, os, secrets
cur = json.load(open("build/env-current.json")) or {}
env = {"SESSION_TTL": "3600", "PASSWORD_HASH": cur["PASSWORD_HASH"], "SESSION_SECRET": cur["SESSION_SECRET"]}
pw = os.environ.get("NEW_PASSCODE")
if pw:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
    env["PASSWORD_HASH"] = f"{salt.hex()}:{digest.hex()}"
    env["SESSION_SECRET"] = secrets.token_hex(32)
json.dump({"Variables": env}, open("build/env.json", "w"))
os.chmod("build/env.json", 0o600)
EOF

aws lambda update-function-configuration --function-name $FN --role $ROLE --runtime python3.13 \
  --handler lambda_function.lambda_handler --timeout 30 --memory-size 256 \
  --environment file://build/env.json --query LastUpdateStatus --output text
aws lambda wait function-updated --function-name $FN
aws lambda update-function-code --function-name $FN --zip-file fileb://build/function.zip --query CodeSize --output text
aws lambda wait function-updated --function-name $FN
rm -f build/env.json build/env-current.json
echo "deployed — https://console.codly.ai/"
