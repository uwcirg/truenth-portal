#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"

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
        "\${DOCKER_TAGS}" - List of tags to apply to image

    Optional overrides:
        "\${DOCKER_REPOSITORY}"
        "\${DOCKER_IMAGE_NAME}"
        "\${DOCKER_IMAGE_TAG}"
        "\${DOCKER_EXTRA_TAGS}" - Additional (space-separated) tags to apply to image
USAGE
   exit 1
}


if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi

. "${bin_path}/utils.sh"

# Default values (mirrors values in docker-compose.yaml)
DOCKER_REPOSITORY="${DOCKER_REPOSITORY-uwcirg-portal-docker.jfrog.io/}"
DOCKER_IMAGE_NAME="${DOCKER_IMAGE_NAME:-portal_web}"
DOCKER_IMAGE_TAG="${DOCKER_IMAGE_TAG:-latest}"
DOCKER_TAGS="${DOCKER_TAGS:-$(get_docker_tags)}"

get_configured_registries | while read config ; do
    repo="$(echo "$config" | cut --delimiter ' ' --fields 1)"

    # Apply all tags in DOCKER_TAGS to image
    echo "$DOCKER_TAGS" | while read tag ; do
        # docker.io is the default repo that `docker push` pushes to
        # if 'docker.io' is included in the command, the push will fail
        if [ "$repo" = "docker.io" ]; then
            docker tag \
                "${DOCKER_REPOSITORY}${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" \
                "${DOCKER_IMAGE_NAME}:${tag}"
        else
            docker tag \
                "${DOCKER_REPOSITORY}${DOCKER_IMAGE_NAME}:${DOCKER_IMAGE_TAG}" \
                "${repo}/${DOCKER_IMAGE_NAME}:${tag}"
        fi
    done

    # Push each tag, in background
    echo "Pushing images to $repo..."
    echo "$DOCKER_TAGS" | while read tag ; do
        if [ "$repo" = "docker.io" ]; then
            docker push "${DOCKER_IMAGE_NAME}:${tag}"
        else
            docker push "${repo}/${DOCKER_IMAGE_NAME}:${tag}"
        fi
        echo "Pushed ${repo}/${DOCKER_IMAGE_NAME}:${tag}"
    done #&
done

# todo: figure out why TravisCI won't wait
# Wait for background jobs to finish
# wait
