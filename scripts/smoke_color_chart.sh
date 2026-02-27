#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${EXPO_PUBLIC_API_BASE_URL:-}}"
TOKEN="${2:-${EXPO_PUBLIC_DEV_ID_TOKEN:-}}"
FIRST_NAME="${3:-Steve}"
LAST_NAME="${4:-Walker}"

if [[ -z "$BASE_URL" || -z "$TOKEN" ]]; then
  cat <<'EOF'
Usage:
  smoke_color_chart.sh [BASE_URL] [TOKEN] [FIRST_NAME] [LAST_NAME]

Env fallback:
  EXPO_PUBLIC_API_BASE_URL
  EXPO_PUBLIC_DEV_ID_TOKEN

Example (from repo root):
  set -a; source myguestv2front/.env; set +a; \
  bash myguestv2back/scripts/smoke_color_chart.sh
EOF
  exit 1
fi

BASE_URL="${BASE_URL%/}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

request() {
  local method="$1"
  local path="$2"
  local outfile="$3"
  curl -sS -X "$method" \
    -H "Accept: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -o "$outfile" \
    -w "%{http_code}" \
    "$BASE_URL$path"
}

echo "== Auth sync =="
auth_status="$(request POST "/auth/sync" "$TMP/auth.json")"
echo "POST /auth/sync -> $auth_status"
if [[ "$auth_status" -ge 400 ]]; then
  cat "$TMP/auth.json"
  exit 2
fi

echo
echo "== Clients lookup: ${FIRST_NAME} ${LAST_NAME} =="
clients_status="$(request GET "/clients?limit=100&offset=0&sort=first_name&order=asc" "$TMP/clients.json")"
echo "GET /clients -> $clients_status"
if [[ "$clients_status" -ge 400 ]]; then
  cat "$TMP/clients.json"
  exit 3
fi

client_id="$(
python3 - "$TMP/clients.json" "$FIRST_NAME" "$LAST_NAME" <<'PY'
import json,sys
path,first,last=sys.argv[1],sys.argv[2].strip().lower(),sys.argv[3].strip().lower()
data=json.load(open(path))
items=data.get("items",[])
for item in items:
    f=(item.get("first_name") or "").strip().lower()
    l=(item.get("last_name") or "").strip().lower()
    if f==first and l==last:
        print(item.get("id"))
        break
PY
)"

if [[ -z "$client_id" ]]; then
  echo "Client not found in /clients response."
  exit 4
fi
echo "Found client_id=$client_id"

echo
echo "== Color chart routes =="
charts_status="$(request GET "/color-charts?limit=500&offset=0" "$TMP/charts.json")"
echo "GET /color-charts -> $charts_status"

if [[ "$charts_status" -eq 404 ]]; then
  echo "Route missing on deployed backend."
elif [[ "$charts_status" -ge 400 ]]; then
  cat "$TMP/charts.json"
  exit 5
else
  python3 - "$TMP/charts.json" "$client_id" <<'PY'
import json,sys
path,cid=sys.argv[1],str(sys.argv[2])
data=json.load(open(path))
items=data.get("items",[])
matches=[x for x in items if str(x.get("client_id") or x.get("clientId"))==cid]
print(f"Bulk matches for client_id={cid}: {len(matches)}")
if matches:
    m=matches[0]
    keys=["id","client_id","porosity","hair_texture","elasticity","scalp_condition","natural_level","desired_level","contrib_pigment","gray_front","gray_sides","gray_back","skin_depth","skin_tone","eye_color"]
    out={k:m.get(k) for k in keys if k in m}
    print("Sample:", json.dumps(out))
PY
fi

for path in \
  "/clients/${client_id}/color-chart" \
  "/clients/${client_id}/colorchart" \
  "/client/${client_id}/colorchart"
do
  status="$(request GET "$path" "$TMP/one.json")"
  printf "GET %s -> %s\n" "$path" "$status"
done

echo
echo "Smoke check complete."
