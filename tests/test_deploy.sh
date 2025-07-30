#!/bin/sh
set -e

cmdname="$(basename "$0")"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
   cat << USAGE >&2
Usage:
   ${cmdname} [-h] [--help]

   -h
   --help
          Show this help message

    Build, start and test docker compose deployment
USAGE
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

PATH="${PATH}:${repo_root}/bin"

# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_root}/docker"
cd "${docker_compose_directory}"

# use production overrides to include healthcheck config
export COMPOSE_FILE=docker-compose.yaml:docker-compose.prod.yaml

# save environment variables to required env_file
env | grep -e SECRET_KEY -e SERVER_NAME > "$PORTAL_ENV_FILE"

docker-build.sh

# deploy docker with locally-built docker image (ie don't pull latest image)
# use force (-f) to bypass inactivity check
deploy-docker.sh -n -f

# sleep until after first healthcheck occurs
sleep 6m
docker compose logs web

web_health="$(docker inspect --format "{{ .State.Health.Status }}" $(docker compose ps --quiet web))"
docker compose down --volumes

if [ "$web_health" = healthy ]; then
    echo "Web process healthy; exiting"
    exit 0
fi

>&2 echo "Error: web process not healthy"
exit 1
