#!/bin/sh -e

cmdname="$(basename "$0")"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
   cat << USAGE >&2
Usage:
   ${cmdname} [-h] [--help]

   -h
   --help
          Show this help message

    Transform translations from PO format to i18next JSON format
USAGE
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

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
        echo "Creating new virtual environment for NodeJS..."
        pip install nodeenv
        nodeenv "${node_venv_path}"
    fi

    deactivate
}
python_venv="${repo_root}/env"
setup_python_venv "${python_venv}"

node_venv="${repo_root}/node_env"
setup_node_venv "${python_venv}" "${node_venv}"

echo "Activating NodeJS virtual environment..."
. "${node_venv}/bin/activate"

echo "Installing NodeJS dependencies..."
npm --prefix "${repo_root}/portal" install

PATH="${PATH}:${repo_root}/portal/node_modules/gulp/bin"
GULPFILE="${repo_root}/portal/i18next_gulpfile.js"
echo "Running tasks..."

echo "Converting translations from PO to JSON format"
gulp.js --gulpfile "$GULPFILE" i18nextConvertPOToJSON

echo "Combining front-end and back-end translation files"
gulp.js --gulpfile "$GULPFILE" combineTranslationJsons
