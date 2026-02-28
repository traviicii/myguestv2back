#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${EXPO_PUBLIC_API_BASE_URL:-}}"
TOKEN="${2:-${EXPO_PUBLIC_DEV_ID_TOKEN:-}}"

if [[ -z "${BASE_URL}" || -z "${TOKEN}" ]]; then
  cat <<'EOF'
Usage:
  smoke_render_contract.sh [BASE_URL] [TOKEN]

Example:
  bash myguestv2back/scripts/smoke_render_contract.sh \
    "https://myguestv2back.onrender.com/api/v1" "$EXPO_PUBLIC_DEV_ID_TOKEN"
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
  local body="${4:-}"
  if [[ -n "${body}" ]]; then
    curl -sS -X "${method}" \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${TOKEN}" \
      -d "${body}" \
      -o "${outfile}" \
      -w "%{http_code}" \
      "${BASE_URL}${path}"
  else
    curl -sS -X "${method}" \
      -H "Accept: application/json" \
      -H "Authorization: Bearer ${TOKEN}" \
      -o "${outfile}" \
      -w "%{http_code}" \
      "${BASE_URL}${path}"
  fi
}

echo "== Basic health =="
health_code="$(curl -sS -o "$TMP/health.json" -w "%{http_code}" "${BASE_URL}/health")"
echo "GET /health -> ${health_code}"
if [[ "${health_code}" -ge 400 ]]; then
  cat "$TMP/health.json"
  exit 2
fi

echo
echo "== Auth sync =="
sync_code="$(request POST "/auth/sync" "$TMP/sync.json" "{}")"
echo "POST /auth/sync -> ${sync_code}"
if [[ "${sync_code}" -ge 400 ]]; then
  cat "$TMP/sync.json"
  exit 3
fi

echo
echo "== OpenAPI route check =="
openapi_url="${BASE_URL%/api/v1}/openapi.json"
openapi_code="$(curl -sS -o "$TMP/openapi.json" -w "%{http_code}" "${openapi_url}")"
if [[ "${openapi_code}" -ge 400 ]]; then
  echo "GET /openapi.json -> ${openapi_code}"
  cat "$TMP/openapi.json"
  exit 4
fi
has_route="$(
python3 - "$TMP/openapi.json" <<'PY'
import json,sys
paths=json.load(open(sys.argv[1])).get("paths", {})
print("/api/v1/clients/{client_id}/color-chart" in paths)
PY
)"
echo "OpenAPI includes /api/v1/clients/{client_id}/color-chart -> ${has_route}"

echo
echo "== Services + formulas list =="
services_code="$(request GET "/services?active=all" "$TMP/services.json")"
formulas_code="$(request GET "/formulas?limit=5&offset=0" "$TMP/formulas.json")"
echo "GET /services?active=all -> ${services_code}"
echo "GET /formulas?limit=5&offset=0 -> ${formulas_code}"

if [[ "${services_code}" -ge 400 ]]; then
  echo "-- /services response --"
  cat "$TMP/services.json"
fi
if [[ "${formulas_code}" -ge 400 ]]; then
  echo "-- /formulas response --"
  cat "$TMP/formulas.json"
fi

echo
echo "== Namespaced CRUD + cleanup =="
stamp="$(date +%s)"
fname="Audit${stamp}"
lname="Contract"
payload="{\"first_name\":\"${fname}\",\"last_name\":\"${lname}\"}"
create_code="$(request POST "/clients" "$TMP/create_client.json" "${payload}")"
echo "POST /clients -> ${create_code}"
if [[ "${create_code}" -ne 201 ]]; then
  cat "$TMP/create_client.json"
  exit 5
fi

client_id="$(
python3 - "$TMP/create_client.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1])).get("id",""))
PY
)"
if [[ -z "${client_id}" ]]; then
  echo "Missing client_id in create response."
  cat "$TMP/create_client.json"
  exit 6
fi
echo "client_id=${client_id}"

chart_payload='{"porosity":"Medium","hair_texture":"Wavy","natural_level":"5","desired_level":"8"}'
patch_code="$(request PATCH "/clients/${client_id}/color-chart" "$TMP/patch_chart.json" "${chart_payload}")"
get_chart_code="$(request GET "/clients/${client_id}/color-chart" "$TMP/get_chart.json")"
delete_code="$(request DELETE "/clients/${client_id}" "$TMP/delete_client.json")"
verify_delete_code="$(request GET "/clients/${client_id}" "$TMP/get_after_delete.json")"

echo "PATCH /clients/${client_id}/color-chart -> ${patch_code}"
echo "GET /clients/${client_id}/color-chart -> ${get_chart_code}"
echo "DELETE /clients/${client_id} -> ${delete_code}"
echo "GET /clients/${client_id} (after delete) -> ${verify_delete_code}"

echo
echo "== Result summary =="
failed=0
if [[ "${has_route}" != "True" ]]; then
  echo "FAIL: missing OpenAPI path /clients/{client_id}/color-chart"
  failed=1
fi
for code in "${services_code}" "${formulas_code}"; do
  if [[ "${code}" -ge 400 ]]; then
    failed=1
  fi
done
if [[ "${patch_code}" -ge 400 || "${get_chart_code}" -ge 400 || "${delete_code}" -ge 400 ]]; then
  failed=1
fi

if [[ "${failed}" -eq 1 ]]; then
  echo "Smoke contract check FAILED."
  exit 7
fi

echo "Smoke contract check PASSED."
