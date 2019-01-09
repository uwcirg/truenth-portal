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

echo "Compiling LESS files..."
nodejs-wrapper.sh gulp.js --gulpfile "${GULPFILE}" epromsLess
nodejs-wrapper.sh gulp.js --gulpfile "${GULPFILE}" gilLess
nodejs-wrapper.sh gulp.js --gulpfile "${GULPFILE}" portalLess
nodejs-wrapper.sh gulp.js --gulpfile "${GULPFILE}" psaTrackerLess
nodejs-wrapper.sh gulp.js --gulpfile "${GULPFILE}" topnavLess
