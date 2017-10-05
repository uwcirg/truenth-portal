#!/bin/sh -e
# docker-compose deployment script
# Build or update a set of containers as defined by a docker-compose.yaml file
# Environmental variables passed to this script (eg IMAGE_TAG) will be available to the given docker-compose.yaml file

cmdname=$(basename $0)

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


repo_path=$( cd $(dirname $0) ; git rev-parse --show-toplevel )

# git-specific environmental variables
# allow git commands outside repo path
export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"

# Set default docker-compose file if COMPOSE_FILE environmental variable not set
export COMPOSE_FILE=${COMPOSE_FILE:-"${GIT_WORK_TREE}/docker/docker-compose.yaml"}

# Set env vars in docker-compose file; see env.default
set -o allexport # export all new env vars by default
. "${GIT_WORK_TREE}/docker/.env"

if [ -n "$BACKUP" -a -n "$(docker-compose ps -q db)" ]; then
    web_image_id="$(docker-compose images -q web)"
    dump_filename="psql_dump-$(date --iso-8601=seconds)-${web_image_id}.pgdump"

    echo "Backing up current database..."
    docker-compose exec --user postgres db pg_dump --format c portaldb > "/tmp/${dump_filename}"
fi

docker-compose pull
docker-compose up -d
