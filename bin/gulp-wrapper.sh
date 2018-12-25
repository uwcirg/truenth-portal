#!/bin/sh -e

cmdname="$(basename "$0")"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
   cat << USAGE >&2
Usage:
   ${cmdname} [-h] [--help] [gulp_task_name]

   -h
   --help
          Show this help message

    gulp_task_name
          Name of gulp task to run

    Run gulp i18n tasks
USAGE
}



setup_python_venv() {
    # Setup a python virtual environment on the given path, if not present
    python_venv_path="$1"
    if [ ! -d "${python_venv_path}" ]; then
        echo "Creating new Python virtual environment..."
        virtualenv "${python_venv_path}"
    fi
}

setup_node_venv() {
    # Setup a virtual environment for NodeJS on the given path, if not present

    python_venv_path="$1"
    # Use existing python virtual environment to install nodeenv module
    . "${python_venv_path}/bin/activate"

    node_venv_path="$2"
    if [ ! -d "${node_venv_path}" ]; then
        pip install nodeenv
        echo "Creating new virtual environment for NodeJS..."
        nodeenv "${node_venv_path}"
    fi

    deactivate
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

python_venv="${repo_root}/env"
setup_python_venv "${python_venv}"

node_venv="${repo_root}/node_env"
setup_node_venv "${python_venv}" "${node_venv}"

echo "Activating NodeJS virtual environment..."
. "${node_venv}/bin/activate"

echo "Installing NodeJS dependencies..."
npm --prefix "${repo_root}/app" install

PATH="${PATH}:${repo_root}/app/node_modules/gulp-cli/bin"
GULPFILE="${repo_root}/app/i18next_gulpfile.js"

gulp_task_name="$1"
echo "Running task $gulp_task_name..."
gulp.js --gulpfile "$GULPFILE" "$gulp_task_name"
