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
    Build a docker image from the current git checkout

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

# Use .gitignore as .dockerignore during build only
# not worth the effort to maintain both, for now
copy_output="$(
    cp \
        --no-clobber \
        --verbose \
        "${root_path}/.gitignore" \
        "${root_path}/.dockerignore"
)"

default_compose_file="${root_path}/docker/docker-compose.yaml"
export COMPOSE_FILE="${COMPOSE_FILE:-$default_compose_file}"

echo "Building portal docker image..."
docker-compose build web

if echo "$copy_output" | grep --quiet "\->"; then
    echo "Deleting generated .dockerignore..."
    rm "${root_path}/.dockerignore"
fi
