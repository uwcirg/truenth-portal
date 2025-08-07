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

    Build all front-end files
USAGE
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

PATH="${PATH}:${repo_root}/bin"
GULPFILE="${repo_root}/portal/development_gulpfile.mjs"


echo "Building front-end files..."
nodejs-wrapper.sh \
    npm --prefix "${repo_root}/portal" run build

echo "Copying substudy template file..."
COPY ${repo_root}/portal/static/templates /opt/venvs/portal/lib/python3.9/site-packages/portal/static/templates/
COPY ${repo_root}/portal/static/dist /opt/venvs/portal/lib/python3.9/site-packages/portal/static/dist/
