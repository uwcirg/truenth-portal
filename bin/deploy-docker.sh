#!/bin/sh -e
# docker-compose deployment script
# Build or update a set of containers as defined by a docker-compose.yaml file
# Environmental variables passed to this script (eg IMAGE_TAG) will be available to the given docker-compose.yaml file

repo_path=$( cd $(dirname $0) ; git rev-parse --show-toplevel )

# git-specific environmental variables
# allow git commands outside repo path
export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"

# Set default docker-compose file if COMPOSE_FILE environmental variable not set
export COMPOSE_FILE=${COMPOSE_FILE:-"${GIT_WORK_TREE}/docker/docker-compose.yaml"}

docker-compose pull
docker-compose up -d
