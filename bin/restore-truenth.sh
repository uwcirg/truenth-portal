#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
repo_path="${bin_path}/.."


usage() {
    cat << USAGE >&2
Usage:
    $cmdname

    Restore a deployment from archived files


USAGE
    exit 1
}


while getopts "hs:u:" option; do
    case "${option}" in
        s)
            sql_dump="${OPTARG}"
            ;;
        u)
            uploads_dir="${OPTARG}"
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


# sql_dump is set via getopts while loop
default_sql_dump=foo.sql
SQL_DUMP="${sql_dump:-$default_sql_dump}"

# uploads_dir is set via getopts while loop
default_uploads_dir=/tmp/bar
UPLOADS_DIR="${uploads_dir:-$default_uploads_dir}"

# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"


if [ -n "$SQL_DUMP" ]; then
    echo $SQL_DUMP
fi

if [ -n "$UPLOADS_DIR" ]; then
    echo $UPLOADS_DIR
fi
