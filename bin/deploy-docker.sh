#!/bin/sh -e
# docker-compose deployment script
# Build or update a set of containers as defined by a docker-compose.yaml file
# Environment variables passed to this script (eg IMAGE_TAG) will be available to the given docker-compose.yaml file

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
repo_path="${bin_path}/.."

usage() {
    cat << USAGE >&2
Usage:
    $cmdname [-b] [-h]
    -b     Backup current database before attempting update
    -n     Do not pull docker images prior to starting
    -h     Show this help message
USAGE
    exit 1
}

while getopts "bhn" option; do
    case "${option}" in
        b)
            BACKUP=true
            ;;
        h)
            usage
            ;;
        n)
            NO_PULL=true
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))


# git-specific environment variables
# allow git commands outside repo path
export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"
# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"

# Bring env vars set in docker/.env into current shell
if [ -f "${GIT_WORK_TREE}/docker/.env" ]; then
    # export all new env vars by default
    set -o allexport
    . "${GIT_WORK_TREE}/docker/.env"
fi


if [ -n "$BACKUP" ] && [ -n "$(docker-compose ps -q db)" ]; then
    web_image_hash="$(docker-compose images -q web | cut -c1-7)"
    dump_filename="psql_dump-$(date --iso-8601=seconds)-${web_image_hash}-${COMPOSE_PROJECT_NAME}"

    echo "Backing up current database..."
    docker-compose exec --user postgres db bash -c '\
        pg_dump \
            --dbname $POSTGRES_DB \
            --no-acl \
            --no-owner \
            --encoding utf8 '\
    > "/tmp/${dump_filename}.sql"
fi

if [ -z "$NO_PULL" ]; then
    echo "Updating images..."
    docker-compose pull
fi

echo "Starting containers..."
# Capture stderr to check for restarted containers
# shell idiom: stderr and stdout file descriptors are swapped and stderr `tee`d
# allows output to terminal and saving to local variable
restarted_containers="$(docker-compose up --detach web 3>&2 2>&1 1>&3 3>&- | tee /dev/stderr)"
