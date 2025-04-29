#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
repo_path="${bin_path}/.."


usage() {
    cat << USAGE >&2
Usage:
    ${cmdname} [-h] upload_dir

    Restore uploaded files for a deployment from given upload directory

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

UPLOADS_DIR="$1"
if [ ! -d "$UPLOADS_DIR" ]; then
    echo "Error: ${UPLOADS_DIR} is not a directory"
    exit 1
fi

restore_uploads() {
    # restore user uploads from given directory
    local uploads_dir="$1"

    # todo: remove DEBUG output from stdout when running `flask config`
    local web_file_upload_dir="$(
        docker compose exec web \
            flask config -c FILE_UPLOAD_DIR \
        | grep --invert-match DEBUG | tr --delete '[:space:]'
    )"
    local run_user="$(docker compose exec web printenv RUN_USER | tr --delete [:space:])"
    local web_container_id=$(docker compose ps --quiet web)

    echo "Copying files from ${uploads_dir} to container upload dir (${web_file_upload_dir})..."
    # copy each file individually, to avoid overwriting entire upload directory
    find "${uploads_dir}" -type f -exec \
        docker cp {} ${web_container_id}:"${web_file_upload_dir}" \; -print
    echo "Done copying uploaded files into container"

    echo "Setting ownership to web user..."
    docker compose exec --user root web \
        chown --recursive "${run_user}:${run_user}" "${web_file_upload_dir}"
    echo "Finished importing uploads"
}

# docker-compose commands must be run in the same directory as docker-compose.yaml
docker_compose_directory="${repo_path}/docker"
cd "${docker_compose_directory}"


restore_uploads "$UPLOADS_DIR"
