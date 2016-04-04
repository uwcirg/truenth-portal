#!/bin/bash

usage() {
    echo "$0 - Simple script to make deployments of fresh code a one command operation"
    echo "Usage: $0 [-b <branch>] [-p <path>]"
    exit 1
}

update_repo(){
    git checkout $BRANCH
    git pull origin $BRANCH
}

# Prevent reading virtualenv environmental variables multiple times
activate_once(){
    if [[ $(which python) != "${GIT_WORK_TREE}"* ]]; then
        source "${GIT_WORK_TREE}/bin/activate"
    fi
}

# Defaults
BRANCH="development"
repo_path=$(git rev-parse --show-toplevel)

while getopts ":b:p:" option; do
    case "${option}" in
        b)
            BRANCH=${OPTARG}
            ;;
        p)
            repo_path=${OPTARG}
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))

if [ ! -d "$repo_path/.git" ]; then
    echo 'Bad git repo path'
    exit 1
fi

GIT_WORK_TREE="$repo_path"
GIT_DIR="${GIT_WORK_TREE}/.git"

old_head=$(git rev-parse origin/$BRANCH)

update_repo
new_head=$(git rev-parse origin/$BRANCH)

# New modules, or new seed data
if [[ -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/setup.py) ]]; then
    activate_once
    pip install -e "${GIT_WORK_TREE}"

    ${GIT_WORK_TREE}/manage.py db seed
fi

# DB Changes
if [[ -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/migrations) ]]; then
    activate_once
    ${GIT_WORK_TREE}/manage.py db upgrade
fi

# Any changes
if [[ -n $(git diff $old_head $new_head) ]]; then
    sudo service apache2 restart
fi
