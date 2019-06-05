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

    Build, start and test docker-compose deployment
USAGE
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

PATH="${PATH}:${repo_root}/bin"

# save environment variables to required env file
env | grep -e SECRET_KEY -e SERVER_NAME > "$PORTAL_ENV_FILE"

docker-build.sh

# use locally-created images instead of pulling latest
COMPOSE_FILE=docker-compose.yaml:docker-compose.prod.yaml \
deploy-docker.sh -n

# sleep until after first healthcheck occurs
sleep 6m
docker-compose logs web

web_health="$(docker inspect --format "{{ .State.Health.Status }}" $(docker-compose ps --quiet web))"
docker-compose down --volumes

if [ "$web_health" = healthy ]; then
    echo "Web process healthy; exiting"
    exit 0
fi

>&2 echo "Error: web process not healthy"
exit 1
