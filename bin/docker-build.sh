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


# Create env_file if it doesn't exist
cp \
    --no-clobber \
    "${repo_path}/docker/portal.env.default" \
    "${repo_path}/docker/portal.env"

# Use .gitignore as .dockerignore during build only
# not worth the effort to maintain both, for now
copy_output="$(
    cp \
        --no-clobber \
        --verbose \
        "${repo_path}/.gitignore" \
        "${repo_path}/.dockerignore"
)"

# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"

echo "Building portal docker image..."
docker-compose build web

if echo "$copy_output" | grep --quiet "\->"; then
    rm "${repo_path}/.dockerignore"
    echo "Deleted generated .dockerignore"
fi
