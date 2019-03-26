#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
root_path="${bin_path}/.."


usage() {
   cat << USAGE >&2
Usage:
   $cmdname [-h] [--help]

   -h
   --help
          Show this help message

    Docker build helper script
    Build a docker image from the HEAD commit of the current git checkout

USAGE
   exit 1
}


if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi

# Create env_file if it doesn't exist
cp \
    --no-clobber \
    "${root_path}/docker/portal.env.default" \
    "${root_path}/docker/portal.env"

default_compose_file="${root_path}/docker/docker-compose.yaml:${root_path}/docker/docker-compose.build.yaml"
export COMPOSE_FILE="${COMPOSE_FILE:-$default_compose_file}"


# Build docker image that generates debian package from current repo and branch
docker-compose build builder

# Build debian package from current repo and branch
docker-compose run builder

# Build portal docker image from debian package
docker-compose build web
