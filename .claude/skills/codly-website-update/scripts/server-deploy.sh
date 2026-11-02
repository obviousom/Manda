#!/usr/bin/env bash
# Runs ON the website box (via ssm-run.sh). Idempotent. Backs up, pulls main, ensures nginx serves site/, verifies.
# Aborts BEFORE touching nginx if the pull fails or site/index.html is missing.
set -u
CONF=/etc/nginx/sites-available/default
REPO=/Codly-Website
TS=$(date +%Y%m%d-%H%M%S)
G="sudo -n git -c safe.directory=$REPO -C $REPO"

echo "### backup"
sudo -n tar czf /root/codly-website-backup-$TS.tar.gz -C / Codly-Website && echo "tar ok" || { echo "BACKUP FAILED - abort"; exit 1; }
sudo -n cp -p $CONF /root/nginx-default.bak-$TS && echo "conf backup ok"
echo "disk:"; df -h / | tail -1

echo "### pull"
BEFORE=$($G rev-parse --short HEAD)
$G pull --ff-only origin main 2>&1 | tail -5
AFTER=$($G rev-parse --short HEAD)
echo "HEAD $BEFORE -> $AFTER"
[ -f $REPO/site/index.html ] || { echo "site/index.html missing (pull failed? creds?) - NOT touching nginx"; exit 1; }

echo "### nginx root"
if grep -qE '^\s*root /Codly-Website;' $CONF; then
  sudo -n sed -i 's#^\(\s*\)root /Codly-Website;#\1root /Codly-Website/site;#' $CONF
  echo "root switched to /Codly-Website/site"
fi
if ! grep -q 'absolute_redirect' $CONF || ! grep -q 'requestdemo.html' $CONF; then
  echo "WARNING: redirect block missing from nginx conf - see SKILL.md 'nginx redirects' (old URLs requestdemo/company will 404)"
fi
grep -nE '^\s*root |absolute_redirect|requestdemo|company.html' $CONF

if sudo -n nginx -t 2>&1; then
  sudo -n systemctl reload nginx && echo "reloaded"
else
  echo "nginx -t FAILED - restoring conf"; sudo -n cp -p /root/nginx-default.bak-$TS $CONF; exit 1
fi

echo "### verify (local; wait for old workers to drain)"
sleep 3
for p in / /index.html /pricing.html /roi.html /register.html /assessment.html /assets/css/site.css /requestdemo.html /company.html; do
  printf "%s " $p; curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080$p
done
echo "rollback: sudo git -c safe.directory=$REPO -C $REPO reset --hard $BEFORE   (or untar /root/codly-website-backup-$TS.tar.gz)"
