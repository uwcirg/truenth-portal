#!/bin/sh
set -eux

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

env | grep -e SECRET_KEY -e SERVER_NAME > "$PORTAL_ENV_FILE"

docker-build.sh

COMPOSE_FILE=docker-compose.yaml:docker-compose.prod.yaml \
deploy-docker.sh -n

sleep 6m
docker-compose logs web

health="$(docker inspect --format "{{ .State.Health.Status }}" $(docker-compose ps --quiet web))"
test "$health" = "healthy"
exit_code=$?
docker-compose down --volumes
exit $exit_code
