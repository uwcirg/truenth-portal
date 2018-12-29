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

    Gulp task wrapper

    Runs gulp tasks with node_env, creating virtual environments as necessary
USAGE
}


setup_python_venv() {
    # Setup a python virtual environment on the given path, if not present
    default_python_venv_path="${repo_root}/env"
    python_venv_path="${1:-$default_python_venv_path}"
    if [ -d "${python_venv_path}" ]; then
        # Exit early if python virtual environment exists
        return
    fi

    echo "Creating new Python virtual environment: ${python_venv_path}"
    virtualenv "${python_venv_path}"
}


setup_node_venv() {
    # Setup a virtual environment for NodeJS on the given path, if not present
    default_node_venv_path="${repo_root}/node_env"
    node_venv_path="${2:-$default_node_venv_path}"
    if [ -d "${node_venv_path}" ]; then
        # Exit early if node_env virtual environment exists
        return
    fi

    # Use existing python virtual environment to install nodeenv module
    default_python_venv_path="${repo_root}/env"
    python_venv_path="${1:-$default_python_venv_path}"
    echo "Activating python virtual environment..."
    . "${python_venv_path}/bin/activate"

    echo "Installing node_env"
    pip install nodeenv

    echo "Creating new virtual environment for NodeJS: ${node_venv_path}"
    nodeenv "${node_venv_path}"

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

# Setup virtual environments
setup_python_venv

node_venv="${repo_root}/node_env"
setup_node_venv "" "$node_venv"

echo "Activating NodeJS virtual environment..."
. "${node_venv}/bin/activate"

echo "Installing NodeJS dependencies..."
npm --prefix "${repo_root}/portal" install --no-progress

PATH="${PATH}:${repo_root}/portal/node_modules/gulp/bin"

DEFAULT_GULPFILE="${repo_root}/portal/i18next_gulpfile.js"
GULPFILE="${GULPFILE:-$DEFAULT_GULPFILE}"

gulp_task_name="$1"
echo "Running task ${gulp_task_name}..."
gulp.js --gulpfile "$GULPFILE" "$gulp_task_name"
