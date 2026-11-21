#!/usr/bin/env bash
# Build and (re)deploy the DBOS worker of one environment on dellpromaxgb10.
#   deploy/deploy.sh <main|develop> [git-sha]
# Runs on the self-hosted runner `dellpromaxgb10` (on the host itself).
# Needs the platform (meritum-infra: onprem/dellpromaxgb10/platform/setup.sh):
# network `meritum`, meritum-postgres and ~/meritum/envs/worker-<env>.env.
# Env: CORE_KEY_FILE, a read-only deploy key of meritum-core (BuildKit --ssh),
# and the repository secrets in worker_secrets, set by the deploy job of ci.yml.
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
branch=${1:?usage: deploy.sh <main|develop> [sha]}
sha=${2:-$(git -C "$repo" rev-parse HEAD)}
case "$branch" in main) env=prd ;; develop) env=dev ;; *) echo "only main and develop deploy" >&2; exit 1 ;; esac
state=${M_STATE:-$HOME/meritum}
envfile="$state/envs/worker-$env.env"
container="meritum-worker-$env"
image="meritum-worker:$env-${sha:0:12}"
# Repository secrets the worker container gets. docker run -e NAME copies the
# value from this process's env, so it is never on a command line or on disk;
# an unset secret is left out and the container still starts (worker#28 will
# name it in the readiness report).
# Add a name here and in the env of the Deploy step in .github/workflows/ci.yml.
worker_secrets=(EUVSDISINFO_MCP_API_KEY)
secret_args=()
for name in "${worker_secrets[@]}"; do secret_args+=(-e "$name"); done
# ADR-31: the files volume shared with the backend of this env (meritum-infra#8
# writes both names to the env file); without them the container gets no mount.
env_value() { sed -n "s/^$1=//p" "$envfile" | tail -n 1; }
log() { printf '[meritum-worker] %s\n' "$*" >&2; }

[ -f "$envfile" ] || { echo "::error::$envfile missing: run the platform workflow in meritum-infra"; exit 1; }

volume_args=()
files_volume=$(env_value MERITUM_FILES_VOLUME)
files_dir=$(env_value MERITUM_FILES_DIR)
if [ -n "$files_volume" ] && [ -n "$files_dir" ]; then volume_args=(-v "$files_volume:$files_dir"); fi

labels=(--label meritum.managed=true --label meritum.role=worker --label meritum.env="$env" --label meritum.sha="$sha")
docker build -q --ssh default="${CORE_KEY_FILE:?}" -t "$image" "${labels[@]}" "$repo" >/dev/null
log "built $image"

exec 9>"$state/deploy.lock"
flock 9  # one change at a time on this host

# DBOS system tables in worker_<env>, owned by the worker role; the API role
# gets access to them so it can enqueue (DBOSClient).
docker run --rm --network meritum --env-file "$envfile" "$image" \
  sh -c 'dbos migrate -s "$MERITUM_DBOS_URL" --schema "$MERITUM_DBOS_SCHEMA" -r "$MERITUM_API_ROLE"' >/dev/null
log "DBOS schema migrated"

# --stop-timeout: DBOS gets time to finish the current step; unfinished
# workflows resume on the new container.
docker rm -f "$container" >/dev/null 2>&1 || true
docker run -d --name "$container" --network meritum --restart unless-stopped --stop-timeout 40 \
  "${labels[@]}" --env-file "$envfile" "${volume_args[@]}" "${secret_args[@]}" "$image" >/dev/null
log "started $container"

for i in $(seq 30); do
  if docker logs "$container" 2>&1 | grep -q 'meritum-worker ready'; then break; fi
  [ "$i" = 30 ] && { log "worker did not become ready"; docker logs --tail 50 "$container" >&2; exit 1; }
  sleep 2
done
log "ready"

docker image ls meritum-worker --filter "label=meritum.env=$env" --format '{{.Repository}}:{{.Tag}}' \
  | grep -vx "$image" | xargs -r docker rmi >/dev/null 2>&1 || true
