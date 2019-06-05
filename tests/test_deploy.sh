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

sh -c 'env | grep -e SECRET_KEY -e SERVER_NAME > "$PORTAL_ENV_FILE"'

sh -c "{toxinidir}/bin/docker-build.sh"
sh -c " \
    COMPOSE_FILE=docker-compose.yaml:docker-compose.prod.yaml \
    {toxinidir}/bin/deploy-docker.sh -n \
"

sh -c 'sleep 6m'
sh -c 'docker-compose logs web'

sh -c ' \
    health="$(docker inspect --format "\{\{ .State.Health.Status \}\}" $(docker-compose ps -q web))"; \
    test "$health" = "healthy"; \
    exit_code=$?; \
    docker-compose down --volumes; \
    exit $exit_code \
'
