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

    Extract frontend strings (to JSON) and convert (to POT)
USAGE
}

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

PATH="${PATH}:${repo_root}/bin"

echo "Extracting and transforming frontend strings..."
nodejs-wrapper.sh \
    gulp.js i18nextConvertJSONToPOT \
        --gulpfile "${repo_root}/portal/i18next_gulpfile.mjs"
