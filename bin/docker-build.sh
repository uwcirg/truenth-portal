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

cleanup_generated_dockerignore() {
    local file_copied="$1"
    if [ -n "$file_copied" ]; then
        rm "${repo_path}/.dockerignore"
        echo "Deleted generated .dockerignore"
    fi
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi


# Use .gitignore as .dockerignore during build only
# not worth the effort to maintain both, for now
copy_output="$(
    cp \
        --no-clobber \
        --verbose \
        "${repo_path}/.gitignore" \
        "${repo_path}/.dockerignore"
)"

# "->" will appear in `cp` output if file is sucessfully copied
file_copied="$(echo "$copy_output" | grep "\->" || true)"

# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"


default_portal_env="${PORTAL_ENV_FILE:-portal.env}"

# Create required env_file if it doesn't exist
cp --no-clobber portal.env.default "$default_portal_env"


# use trap to cleanup generated .dockerignore on early exit
trap 'cleanup_generated_dockerignore "$file_copied"; exit' INT TERM EXIT
echo "Building portal docker image..."
docker-compose build web
trap - INT TERM EXIT

cleanup_generated_dockerignore "$file_copied"
