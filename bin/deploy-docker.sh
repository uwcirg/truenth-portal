#!/bin/sh -e
# docker-compose deployment script
# Build or update a set of containers as defined by a docker-compose.yaml file
# Environment variables passed to this script (eg IMAGE_TAG) will be available to the given docker-compose.yaml file

cmdname="$(basename "$0")"

usage() {
    cat << USAGE >&2
Usage:
    $cmdname [-b] [-h]
    -h     Show this help message
    -b     Backup current database before attempting update
USAGE
    exit 1
}

while getopts "bh" option; do
    case "${option}" in
        b)
            BACKUP=true
            ;;
        h)
            usage
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))


repo_path="$(cd "$(dirname "$0")" && git rev-parse --show-toplevel)"

# git-specific environment variables
# allow git commands outside repo path
export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"

# Set default docker-compose file if COMPOSE_FILE environment variable not set
export COMPOSE_FILE="${COMPOSE_FILE:-"${GIT_WORK_TREE}/docker/docker-compose.yaml"}"

# Set env vars in docker-compose file; see env.default
set -o allexport # export all new env vars by default
. "${GIT_WORK_TREE}/docker/.env"

cd "${GIT_WORK_TREE}/docker"

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

echo "Updating images..."
docker-compose pull
echo "Starting containers..."
# Capture stderr to check for restarted containers
# shell idiom: stderr and stdout file descriptors are swapped and stderr `tee`d
# allows output to terminal and saving to local variable
restarted_containers="$(docker-compose up -d web 3>&2 2>&1 1>&3 3>&- | tee /dev/stderr)"

# Set celery CPU limit after start
if echo "$restarted_containers" | grep --ignore-case --quiet 'creating.*celeryworker'; then
    echo "Applying CPU limit to celery worker..."
    docker container update --cpus .3 "$(docker-compose ps --quiet celeryworker)"
fi
