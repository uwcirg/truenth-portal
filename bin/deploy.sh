#!/bin/bash

usage() {
    echo "$0 - Simple script to make deployments of fresh code a one command operation" >&2
    echo "Usage: $0 [-v] [-f] [-b <branch>] [-p <path>]" >&2
    echo -e "\nOptions: " >&2
    echo -e "-v\n Be verbose" >&2
    echo -e "-f\n Force all conditional deployment processes" >&2
    exit 1
}

update_repo(){
    if [[ $VERBOSE ]]; then
        echo "Updating repository"
    fi
    branch_name=$(git symbolic-ref -q HEAD)

    if [[ "$BRANCH" != "$(git symbolic-ref -q HEAD)" ]]; then
        git checkout $BRANCH
    fi

    git pull origin $BRANCH
}

# Prevent reading virtualenv environmental variables multiple times
activate_once(){
    if [[ $(which python) != "${GIT_WORK_TREE}"* ]]; then
        if [[ $VERBOSE ]]; then
            echo "Activating virtualenv"
        fi
        source "${GIT_WORK_TREE}/env/bin/activate"
    fi
}

repo_path=$( cd $(dirname $0) ; git rev-parse --show-toplevel )

while getopts ":b:p:vf" option; do
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
        f)
            FORCE=true
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))

if [ ! -d "$repo_path/.git" ]; then
    echo 'Error: Bad git repo path' >&2
    exit 1
fi

export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"

if [[ -z $BRANCH ]]; then
    BRANCH="develop"

    # Use master branch on production
    if [[ "${GIT_WORK_TREE}" == "/srv/www/us.truenth.org"* ]]; then
        BRANCH="master"
    fi
fi

old_head=$(git rev-parse origin/$BRANCH)

update_repo
new_head=$(git rev-parse origin/$BRANCH)


# New modules
if [[
    $FORCE ||
    ( -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/setup.py) && $? -eq 0 ) ||
    ( -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/requirements.txt) && $? -eq 0 )
]]; then
    activate_once

    if [[ $VERBOSE ]]; then
        echo "Updating python dependancies"
    fi
    cd "${GIT_WORK_TREE}"
    pip install --requirement "${GIT_WORK_TREE}"/requirements.txt "${GIT_WORK_TREE}"

    # Restart in case celery module updates
    sudo service celeryd restart
fi

# DB Changes
if [[ $FORCE || ( -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/migrations) && $? -eq 0 ) ]]; then
    activate_once

    if [[ $VERBOSE ]]; then
        echo "Running database migrations"
    fi
    cd "${GIT_WORK_TREE}"
    python "${GIT_WORK_TREE}/manage.py" db upgrade
fi

# New seed data
if [[ $FORCE || ( -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/portal/models) && $? -eq 0 ) ]]; then
    activate_once

    if [[ $VERBOSE ]]; then
        echo "Seeding database"
    fi
    python "${GIT_WORK_TREE}/manage.py" seed
fi


# Celery Changes
if [[ $FORCE || ( -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}/portal/tasks.py) && $? -eq 0 ) ]]; then
    activate_once

    if [[ $VERBOSE ]]; then
        echo "Restarting celeryd"
    fi
    sudo service celeryd restart
fi

# Code changes - update package metadata
if [[ $FORCE || ( -n $(git diff $old_head $new_head -- ${GIT_WORK_TREE}) && $? -eq 0 ) ]]; then
    activate_once

    if [[ $VERBOSE ]]; then
        echo "Updating package metadata"
    fi
    python "${GIT_WORK_TREE}/setup.py" egg_info
fi

# Restart apache if application is served by apache
if [[ "${GIT_WORK_TREE}" == "/srv/www/"* ]]; then
    if [[ $VERBOSE ]]; then
        echo "Restarting apache"
    fi
    sudo service apache2 restart
fi
