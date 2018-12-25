#!/bin/sh -e

cmdname="$(basename "$0")"

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

    git fetch origin
    git fetch --tags

    # Change current branch, if specified
    if [ -n "$BRANCH" ] && [ "$BRANCH" != "$repo_branch" ]; then
        echo "Switching current branch to $BRANCH"
        git checkout "$BRANCH"
        repo_branch="$BRANCH"
    fi

    git reset --hard "origin/$repo_branch"
}

repo_path="$(cd $(dirname $0) ; git rev-parse --show-toplevel)"

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
    echo 'Error: Bad git repo path' >&2
    exit 1
fi

export GIT_WORK_TREE="$repo_path"
export GIT_DIR="${GIT_WORK_TREE}/.git"
export FLASK_APP="${GIT_WORK_TREE}/manage.py"

repo_branch="$(git rev-parse --abbrev-ref HEAD)"

# Assign branch in the following precedence:
# BRANCH envvar, branch specified by option (-b)
BRANCH="${BRANCH:-${branch}}"
update_repo

virtualenv_path="${GIT_WORK_TREE}/env"
if [ ! -d "${virtualenv_path}" ]; then
    echo "Creating new virtual environment..."
    virtualenv "${virtualenv_path}"
    . "${virtualenv_path}/bin/activate"
    pip install --upgrade pip setuptools
    deactivate
fi

echo "Activating virtualenv"
. "${virtualenv_path}/bin/activate"

echo "Updating python dependancies"
cd "${GIT_WORK_TREE}"
# Do not pass GIT_WORK_TREE environment variable
# Dependencies installed in "editable mode" (-e) with git will not install correctly
env --unset GIT_WORK_TREE pip install --quiet --requirement requirements.txt

echo "Synchronizing database"
flask sync

if [ -n "$(flask config --config_key SMARTLING_USER_SECRET)" ]; then
    echo "Downloading translations from Smartling"
    flask download-translations

    echo "Transforming translations for frontend"
    "${GIT_WORK_TREE}/bin/build-frontend-translations.sh"
fi

echo "Updating package metadata"
python setup.py egg_info --quiet
