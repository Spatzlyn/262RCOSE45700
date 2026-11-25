#!/usr/bin/env bash
# Deploy v1.1 + Track 2 to the EC2 server without losing existing runs.
# Run on the server from the new code folder:  bash backend/deploy/deploy_v11.sh <scorer_commit>
# Expects: code at ~/backend/262 (with backend/.env kept), store at /data/backend-store.
set -euo pipefail
CODE=~/backend/262
STORE=/data/backend-store
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
SC=${1:?scorer commit}
cd "$CODE"

echo "== 1. snapshot before (v1.0 runs and result hashes)"
mkdir -p ~/deploy_logs
curl -sf localhost:8888/api/runs > ~/deploy_logs/runs_before_$STAMP.json || echo "(API not reachable, skipping snapshot)"
for r in $(python3 -c "import json,sys;print(' '.join(x['run_id'] for x in json.load(open(sys.argv[1]))['runs']))" ~/deploy_logs/runs_before_$STAMP.json 2>/dev/null); do
  curl -sf "localhost:8888/api/runs/$r/report" | python3 -c "import json,sys;d=json.load(sys.stdin);print(sys.argv[1], d['versions']['result_hash'])" "$r"
done > ~/deploy_logs/hashes_before_$STAMP.txt || true

echo "== 2. stop writers and back up the store"
sudo systemctl stop road-vlm-worker || true
(cd backend && sudo docker compose stop api) || true
sudo tar -C /data -czf /data/backend-store-backup-$STAMP.tar.gz backend-store
ls -la /data/backend-store-backup-$STAMP.tar.gz

echo "== 3. install v1.1 store files (adds only; v1.0 files untouched)"
python3 -m backend.tools.install_v11 --target "$STORE"
python3 -m backend.tools.install_v11 --target "$STORE" --apply
# reviewed v1.1 GT, A/B runs and Track 2 are new paths: copy without overwriting anything
for p in reference_history_v11 runs/v11_a_e18f74ffcc runs/v11_b_9895a83702 track2; do
  [ -e "backend/store/$p" ] && sudo -u "#1000" mkdir -p "$STORE/$(dirname $p)" && cp -rn "backend/store/$p" "$STORE/$(dirname $p)/"
done
# references_v11: the deployment may hold the PM draft; replace rows only with the newer Reviewed version
python3 - "$STORE" <<'EOF'
import json, sys, pathlib
dest = pathlib.Path(sys.argv[1]) / "references_v11.jsonl"
src = pathlib.Path("backend/store/references_v11.jsonl")
rows = lambda p: {r["item_id"]: r for r in map(json.loads, filter(str.strip, p.read_text(encoding="utf-8").splitlines()))} if p.exists() else {}
cur, new = rows(dest), rows(src)
changed = [i for i, r in new.items() if r.get("annotation_status") == "Reviewed" and cur.get(i, {}).get("reference_version") != r["reference_version"]]
for i in changed: cur[i] = new[i]
dest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in cur.values()), encoding="utf-8")
print("reviewed v1.1 refs set:", changed)
EOF
sudo chown -R 1000:1000 "$STORE"

echo "== 4. rebuild API and restart worker"
(cd backend && sudo SCORER_COMMIT="$SC" docker compose up -d --build) > ~/deploy_logs/compose_$STAMP.log 2>&1 || { tail -40 ~/deploy_logs/compose_$STAMP.log; exit 1; }
grep -E "passed|failed" ~/deploy_logs/compose_$STAMP.log | tail -1
sudo systemctl start road-vlm-worker
for i in $(seq 1 20); do curl -sf localhost:8888/api/health >/dev/null && break; sleep 2; done

echo "== 5. verify: old result hashes must be identical"
while read -r r h; do
  now=$(curl -sf "localhost:8888/api/runs/$r/report" | python3 -c "import json,sys;print(json.load(sys.stdin)['versions']['result_hash'])")
  [ "$now" = "$h" ] && echo "same   $r" || echo "CHANGED $r ($h -> $now)"
done < ~/deploy_logs/hashes_before_$STAMP.txt
curl -sf localhost:8888/api/versions; echo
curl -sf localhost:8888/api/runs | python3 -c "import json,sys;[print(r['run_id'], r.get('status'), r['n_requests']) for r in json.load(sys.stdin)['runs']]"
curl -sf localhost:8888/api/track2/items | python3 -c "import json,sys;print('track2 items', json.load(sys.stdin)['n'])"
echo "backup: /data/backend-store-backup-$STAMP.tar.gz"
