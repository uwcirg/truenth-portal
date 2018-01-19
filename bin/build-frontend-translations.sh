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

setup_node_venv() {
    # Use existing python virtual environment to install nodeenv module
    . "${repo_root}/env/bin/activate"
    pip install nodeenv

    nodeenv "$node_venv"
    deactivate
}

node_venv="${repo_root}/node_env"

if [ ! -d "${node_venv}" ]; then
    echo "Creating new virtual environment for NodeJS..."
    setup_node_venv
fi

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
