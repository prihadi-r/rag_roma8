#!/usr/bin/env bash
# Deploy modul rag_teologi ke 192.168.18.222 dan muat ulang Odoo.
#
#   ./scripts/deploy_module.sh            # unggah + upgrade
#   ./scripts/deploy_module.sh --install  # unggah + install (-i)
#   ./scripts/deploy_module.sh --no-reload # unggah + upgrade, tanpa restart layanan
#
# Membutuhkan .secrets/rsh_pass (lihat scripts/rrun.py).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE="rag_teologi"
MODULE_PATH="$ROOT/module/$MODULE"
DB="${RAG_DB:-rag_roma8}"
MODE="-u"

for arg in "$@"; do
  case "$arg" in
    --install)   MODE="-i" ;;
    --no-reload) RELOAD=0 ;;
    *) echo "argumen tidak dikenal: $arg" >&2; exit 2 ;;
  esac
done
RELOAD="${RELOAD:-1}"

cd "$ROOT"

echo "== 1/4 memeriksa sintaks =="
python3 -m py_compile "$MODULE_PATH"/__init__.py "$MODULE_PATH"/hooks.py "$MODULE_PATH"/models/*.py
find "$MODULE_PATH" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
for f in "$MODULE_PATH"/views/*.xml "$MODULE_PATH"/security/*.xml "$MODULE_PATH"/data/*.xml; do
  python3 -c "import xml.etree.ElementTree as ET,sys; ET.parse(sys.argv[1])" "$f"
done
echo "   ok"

echo "== 2/4 mengemas & mengunggah =="
TAR="$(mktemp -t rag_teologi.XXXXXX.tar.gz)"
tar czf "$TAR" -C "$ROOT/module" "$MODULE"
python3 scripts/rrun.py --put "$TAR" "/tmp/$MODULE.tar.gz"
rm -f "$TAR"

echo "== 3/4 memasang ke addons =="
python3 scripts/rrun.py -t 180 --sudo -s <<EOF
set -e
rm -rf /opt/odoo18/addons/$MODULE
tar xzf /tmp/$MODULE.tar.gz -C /opt/odoo18/addons/
chown -R odoo18:odoo18 /opt/odoo18/addons/$MODULE
chmod -R u+rwX,go+rX /opt/odoo18/addons/$MODULE
echo "   terpasang"
EOF

echo "== 4/4 $MODE modul di database $DB =="
python3 scripts/rrun.py -t 900 --sudo -s <<EOF
cd /opt/odoo18
rm -f /tmp/${MODULE}_deploy.log
sudo -u odoo18 /opt/odoo18/venv/bin/python3.12 /opt/odoo18/odoo-bin \
  -c /etc/odoo18.conf -d $DB $MODE $MODULE \
  --stop-after-init --no-http --logfile=/tmp/${MODULE}_deploy.log --log-level=warn >/dev/null 2>&1
echo "   exit: \$?"
echo "   galat: \$(grep -cE 'ERROR|CRITICAL' /tmp/${MODULE}_deploy.log)"
grep -E "ERROR|CRITICAL" /tmp/${MODULE}_deploy.log | head -5 || true
sudo -u postgres psql -d $DB -tAc "select '   state: '||state from ir_module_module where name='$MODULE'"
EOF

if [ "$RELOAD" = "1" ]; then
  echo "== memuat ulang layanan Odoo =="
  python3 scripts/rrun.py -t 120 --sudo 'systemctl restart odoo18.service; sleep 6; echo "   status: $(systemctl is-active odoo18.service)"'
fi

echo "selesai."
