#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
repo_path="${bin_path}/.."


usage() {
   cat << USAGE >&2
Usage:
   $cmdname [-h] [--help]

   -h
   --help
          Show this help message

    Docker build helper script
    Build a docker image from the current git checkout

USAGE
   exit 1
}


if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi

# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"


default_portal_env="${PORTAL_ENV_FILE:-portal.env}"

# Create required env_file if it doesn't exist
cp --no-clobber portal.env.default "$default_portal_env"

echo "Building portal docker image..."
docker compose build web
