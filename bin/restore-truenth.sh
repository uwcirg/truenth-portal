#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
repo_path="${bin_path}/.."


usage() {
    cat << USAGE >&2
Usage:
    $cmdname [-h] [-s dump.sql] [-u upload_dir]

    Restore a deployment from archived files

    -h     Show this help message
    -s     Restore the databases from given SQL dump
    -u     Restore user uploads from given directory

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


# implement default variables (eg default_sql_dump, default_uploads_dir) as necessary
SQL_DUMP="${sql_dump:-$default_sql_dump}"
UPLOADS_DIR="${uploads_dir:-$default_uploads_dir}"

# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"


if [ -n "$SQL_DUMP" ]; then
    echo "Stopping containers..."
    docker-compose stop web celeryworker celerybeat

    echo "Dropping existing DB..."
    docker-compose exec db dropdb --username postgres portaldb

    echo "Creating empty DB..."
    docker-compose exec db createdb --username postgres portaldb

    echo "Loading SQL dumpfile: ${SQL_DUMP}..."
    # Disable pseudo-tty allocation
    docker-compose exec -T db psql --dbname portaldb --username postgres < "${SQL_DUMP}"
    echo "Loaded SQL dumpfile"
fi

if [ -n "$UPLOADS_DIR" ]; then
    # todo: remove DEBUG output from stdout when running `flask config`
    web_file_upload_dir="$(docker-compose exec web flask config -c FILE_UPLOAD_DIR | grep --invert-match DEBUG | tr --delete '[:space:]')"
    run_user="$(docker-compose exec web printenv RUN_USER)"
    web_container_id=$(docker-compose ps --quiet web)

    echo "Copying files from ${UPLOADS_DIR} to container upload dir (${web_file_upload_dir})..."
    # copy each file individually, to avoid overwriting entire upload directory
    find "${UPLOADS_DIR}" -type f -exec \
        docker cp {} ${web_container_id}:"${web_file_upload_dir}" \; -print
    echo "Setting ownership to web user..."
    docker-compose exec --user root web \
        chown --recursive "$run_user:$run_user" "${web_file_upload_dir}"
    echo "Done copying uploaded files into container"
fi
