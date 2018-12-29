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
GULPFILE="${repo_root}/portal/development_gulpfile.js"

echo "Compiling LESS files"
gulp-wrapper.sh -g "${GULPFILE}" epromsLess
gulp-wrapper.sh -g "${GULPFILE}" gilLess
gulp-wrapper.sh -g "${GULPFILE}" portalLess
gulp-wrapper.sh -g "${GULPFILE}" psaTrackerLess
gulp-wrapper.sh -g "${GULPFILE}" topnavLess
