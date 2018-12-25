#!/bin/sh -e

cmdname="$(basename "$0")"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
   cat << USAGE >&2
Usage:
   ${cmdname} [-h] [-g gulpfile] [gulp_task_name]

   -h
          Show this help message

   -g
          Run task from given gulpfile

    gulp_task_name
          Name of gulp task to run

    Run gulp tasks
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

# Parse and assign options
while getopts "g:h" option; do
    case "${option}" in
        g)
            GULPFILE="${OPTARG}"
            ;;
        h)
            usage
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))

# Setup environments
python_venv="${repo_root}/env"
setup_python_venv "${python_venv}"

node_venv="${repo_root}/node_env"
setup_node_venv "${python_venv}" "${node_venv}"


echo "Activating NodeJS virtual environment..."
. "${node_venv}/bin/activate"

echo "Installing NodeJS dependencies..."
npm --prefix "${repo_root}/portal" install

PATH="${PATH}:${repo_root}/portal/node_modules/gulp/bin"
DEFAULT_GULPFILE="${repo_root}/portal/i18next_gulpfile.js"
GULPFILE="${GULPFILE:-$DEFAULT_GULPFILE}"

gulp_task_name="$1"
echo "Running task $gulp_task_name..."
gulp.js --gulpfile "$GULPFILE" "$gulp_task_name"
