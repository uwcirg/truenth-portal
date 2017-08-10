#!/bin/sh
# Abort script at first error
set -e errexit

repo_path=$( cd $(dirname $0) ; git rev-parse --show-toplevel )

# git-specific environmental variables
# allow git commands outside repo path
export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"

# Set default docker-compose file if COMPOSE_FILE not set
export COMPOSE_FILE=${COMPOSE_FILE:-"${GIT_WORK_TREE}/docker/docker-compose.yaml"}

docker-compose pull
docker-compose up -d
