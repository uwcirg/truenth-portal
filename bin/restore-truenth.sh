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
            SQL_DUMP="${OPTARG}"
            ;;
        u)
            UPLOADS_DIR="${OPTARG}"
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

restore_sqldump() {
    # restore a deployment from a given SQL dump file path
    local sqldump_path="$1"

    echo "Stopping services..."
    docker-compose stop web celeryworker celerybeat

    echo "Dropping existing DB..."
    docker-compose exec db \
        dropdb --username postgres portaldb

    echo "Creating empty DB..."
    docker-compose exec db \
        createdb --username postgres portaldb

    echo "Loading SQL dumpfile: ${sqldump_path}..."
    # Disable pseudo-tty allocation
    docker-compose exec -T db \
        psql --dbname portaldb --username postgres < "${sqldump_path}"
    echo "Loaded SQL dumpfile"
}

restore_uploads() {
    # restore user uploads from given directory
    local uploads_dir="$1"

    # todo: remove DEBUG output from stdout when running `flask config`
    web_file_upload_dir="$(
        docker-compose exec web \
            flask config -c FILE_UPLOAD_DIR \
        | grep --invert-match DEBUG | tr --delete '[:space:]'
    )"
    run_user="$(docker-compose exec web printenv RUN_USER | tr -d [:space:])"
    web_container_id=$(docker-compose ps --quiet web)

    echo "Copying files from ${uploads_dir} to container upload dir (${web_file_upload_dir})..."
    # copy each file individually, to avoid overwriting entire upload directory
    find "${uploads_dir}" -type f -exec \
        docker cp {} ${web_container_id}:"${web_file_upload_dir}" \; -print
    echo "Done copying uploaded files into container"

    echo "Setting ownership to web user..."
    docker-compose exec --user root web \
        chown --recursive "${run_user}:${run_user}" "${web_file_upload_dir}"
    echo "Finished importing uploads"
}


# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"

if [ -n "$SQL_DUMP" ]; then
    restore_sqldump "$SQL_DUMP"
fi

if [ -n "$UPLOADS_DIR" ]; then
    restore_uploads "$UPLOADS_DIR"
fi
