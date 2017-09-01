#!/bin/bash -e

cmdname=$(basename $0)

usage() {
    cat << USAGE >&2
Simple script to make deployments of fresh code a one-command operation"
Usage:
    $cmdname [-b <branch>] [-p <path>]
    -b     Remote branch to checkout (default: develop)
    -p     Path to repository (default: current working directory)
USAGE
    exit 1
}

update_repo(){
    echo "Updating repository"
    branch_name=$(git symbolic-ref -q HEAD)

    git fetch origin
    git fetch --tags

    if [[ "$BRANCH" != "$(git symbolic-ref -q HEAD)" ]]; then
        git checkout $BRANCH
    fi


    git pull origin $BRANCH
}

# Prevent reading virtualenv environmental variables multiple times
activate_once(){
    if [[ $(which python) != "${GIT_WORK_TREE}"* ]]; then
        echo "Activating virtualenv"
        source "${GIT_WORK_TREE}/env/bin/activate"
    fi
}

repo_path=$( cd $(dirname $0) ; git rev-parse --show-toplevel )

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
    echo 'Error: Bad git repo path' >&2
    exit 1
fi

export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"
export FLASK_APP="${GIT_WORK_TREE}/manage.py"

if [[ -z $BRANCH ]]; then
    BRANCH="develop"

    # Use master branch on production
    if [[ "${GIT_WORK_TREE}" == "/srv/www/us.truenth.org"* ]]; then
        BRANCH="master"
    fi
fi

update_repo
activate_once

echo "Updating python dependancies"
cd "${GIT_WORK_TREE}"
env --unset GIT_WORK_TREE pip install --quiet --requirement requirements.txt

echo "Synchronizing database"
flask sync

echo "Updating package metadata"
python setup.py egg_info --quiet

# Restart apache if application is served by apache
if [[ "${GIT_WORK_TREE}" == "/srv/www/"* ]]; then
    echo "Restarting services"
    sudo service apache2 restart
    sudo service celeryd restart
fi
