#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
repo_path="${bin_path}/.."


usage() {
    cat << USAGE >&2
Usage:
    ${cmdname} [-h] dump.sql

    Restore a deployment from a given SQL dump file

    -h
    --help
        Show this help message

USAGE
    exit 1
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

SQL_DUMP="$1"
if [ ! -s "$SQL_DUMP" ]; then
    echo "Error: ${SQL_DUMP} is not non-zero file"
    exit 1
fi

restore_sqldump() {
    # restore a deployment from a given SQL dump file path
    local sqldump_path="$1"

    echo "Stopping services..."
    docker compose stop web celeryworker celeryworkerslow celerybeat

    echo "Dropping existing DB..."
    docker compose exec db \
        dropdb --username postgres portaldb

    echo "Creating empty DB..."
    docker compose exec db \
        createdb --username postgres portaldb

    echo "Loading SQL dumpfile: ${sqldump_path}..."
    # Disable pseudo-tty allocation
    docker compose exec -T db \
        psql --dbname portaldb --username postgres < "${sqldump_path}"
    echo "Loaded SQL dumpfile"
}

# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"


restore_sqldump "$SQL_DUMP"
