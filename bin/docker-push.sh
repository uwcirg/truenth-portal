#!/bin/sh -e

cmdname="$(basename $0)"
bin_path="$( cd $(dirname $0) && pwd )"

usage() {
   cat << USAGE >&2
Usage:
   $cmdname [-h] [--help]

   -h
   --help
          Show this help message

    Docker delivery helper script

    Tag and push any docker registry configured with associated environment variables:
        "\${REGISTRY}_USERNAME"
        "\${REGISTRY}_API_KEY"
        "\${REGISTRY}_REPO"
        "\${DOCKER_TAGS}"

    Optional overrides:
        "\${DOCKER_REPOSITORY}"
        "\${DOCKER_IMAGE_NAME}"
        "\${DOCKER_IMAGE_TAG}"
USAGE
   exit 1
}

if [ "$1" = "-h" -o "$1" = "--help" ]; then
    usage
fi

. "$bin_path/utils.sh"

# Default values (mirrors values in docker-compose.yaml)
DOCKER_REPOSITORY="${DOCKER_REPOSITORY-uwcirg-portal-docker.jfrog.io/}"
DOCKER_IMAGE_NAME="${DOCKER_IMAGE_NAME:-portal_web}"
DOCKER_IMAGE_TAG="${DOCKER_IMAGE_TAG:-latest}"

get_configured_registries | while read config ; do

    repo="$(echo "$config" | awk '{print $1}')"
    username="$(echo "$config" | awk '{print $2}')"
    api_key="$(echo "$config" | awk '{print $3}')"

    # Apply all tags in DOCKER_TAGS to image
    for tag in $DOCKER_TAGS; do
        docker tag \
            "${DOCKER_REPOSITORY}${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" \
            "${repo}/${DOCKER_IMAGE_NAME}:${tag}"
    done

    # Push each tag, in background
    for tag in $DOCKER_TAGS; do
        docker push "${repo}/${DOCKER_IMAGE_NAME}:${tag}"
    done &

done

# Wait for background jobs to finish
wait
