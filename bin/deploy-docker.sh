#!/bin/sh
# Abort script at first error
set -e errexit

repo_path=$( cd $(dirname $0) ; git rev-parse --show-toplevel )
export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"

export COMPOSE_FILE="${GIT_WORK_TREE}/docker/docker-compose.yaml"

docker-compose pull
docker-compose up -d
