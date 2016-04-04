#!/bin/bash

usage() {
    echo "$0 - Simple script to make deployments of fresh code a one command operation"
    echo "Usage: $0 [-b <branch>] [-p <path>]"
    exit 1
}

update_repo(){
    git checkout $branch
    git pull origin $branch
}

# Prevent reading virtualenv environmental variables multiple times
activate_once(){
    if [[ $(which python) != "$repo_path"* ]]; then
        source $repo_path/bin/activate
    fi
}

# Defaults
branch="development"
repo_path=$(git rev-parse --show-toplevel)

while getopts ":b:p:" option; do
    case "${option}" in
        b)
            branch=${OPTARG}
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

old_head=$(git rev-parse origin/$branch)

update_repo
new_head=$(git rev-parse origin/$branch)

# New modules, or new seed data
if [[ -n $(git diff $old_head $new_head $repo_path/setup.py) ]]; then
    activate_once
    pip install -e $repo_path

    $repo_path/manage.py db seed
fi

# DB Changes
if [[ -n $(git diff $old_head $new_head $repo_path/migrations) ]]; then
    activate_once
    $repo_path/manage.py db upgrade
fi

# Any changes
if [[ -n $(git diff $old_head $new_head) ]]; then
    service apache2 restart
fi
