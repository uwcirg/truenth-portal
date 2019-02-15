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

    Pre-build helper script

    Runs steps necessary to prepare source for building debian package

USAGE
   exit 1
}


if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
fi

# version given by setuptools_scm
# run on clean checkout to avoid "dirty" version numbers (indicating local changes)
version="$(python setup.py --version)"

# Add changelog entry with last commit message
echo "Creating changelog entry for version ${version}..."
debchange "$(git log -1 --pretty=%B)" \
    --maintmaint \
    --newversion "$version"

# ignore updates to changelog to prevent "dirty" version numbers (indicating local changes)
git update-index --skip-worktree debian/changelog
