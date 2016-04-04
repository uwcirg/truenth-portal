#!/bin/bash

usage() {
    echo "$0 - Simple script to make deployments of fresh code a one command operation"
    echo "Usage: $0 [-v] [-b <branch>] [-p <path>]"
    exit 1
}

update_repo(){
    if [[ $VERBOSE ]]; then
        echo "Updating repository"
    fi
    git checkout $BRANCH
    git pull origin $BRANCH
}

# Prevent reading virtualenv environmental variables multiple times
activate_once(){
    if [[ $(which python) != "${GIT_WORK_TREE}"* ]]; then
        if [[ $VERBOSE ]]; then
            echo "Activating virtualenv"
        fi
        source "${GIT_WORK_TREE}/bin/activate"
    fi
}

# Defaults
BRANCH="development"
repo_path=$( cd $(dirname $0) ; git rev-parse --show-toplevel )

while getopts ":b:p:v" option; do
    case "${option}" in
        b)
            BRANCH=${OPTARG}
            ;;
        p)
            repo_path=${OPTARG}
            ;;
        v)
            VERBOSE=true
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

export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"

old_head=$(git rev-parse origin/$BRANCH)

update_repo
new_head=$(git rev-parse origin/$BRANCH)

# New modules, or new seed data
if [[ -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/setup.py) ]]; then
    activate_once

    if [[ $VERBOSE ]]; then
        echo "Updating python dependancies"
    fi
    pip install -e "${GIT_WORK_TREE}"

    if [[ $VERBOSE ]]; then
        echo "Seeding database"
    fi
    python "${GIT_WORK_TREE}/manage.py" db seed
fi

# DB Changes
if [[ -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/migrations) ]]; then
    activate_once

    if [[ $VERBOSE ]]; then
        echo "Running database migrations"
    fi
    cd "${GIT_WORK_TREE}"
    python "${GIT_WORK_TREE}/manage.py" db upgrade
fi

# Restart apache if application is served by apache
if [[ "${GIT_WORK_TREE}" == "/srv/www/"* && -n $(git diff $old_head $new_head) ]]; then
    if [[ $VERBOSE ]]; then
        echo "Restarting apache"
    fi
    sudo service apache2 restart
fi
