#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"
root_path="${bin_path}/.."


usage() {
   cat << USAGE >&2
Usage:
   $cmdname [-h] [--help]

   -h
   --help
          Show this help message

    Post-build helper script

    Runs steps necessary after package building

USAGE
   exit 1
}
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi


echo "Moving debian package file from working directory to artifact directory..."
mv --verbose "${root_path}"/../portal_*.deb "${ARTIFACT_DIR}"

echo "Building package list for local repo..."
cd "${ARTIFACT_DIR}"
dpkg-scanpackages . | gzip > "${ARTIFACT_DIR}/Packages.gz"

chown --verbose nobody:nogroup "${ARTIFACT_DIR}/"*
