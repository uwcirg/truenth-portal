#!/bin/sh -e

cmdname="$(basename "$0")"
bin_path="$(cd "$(dirname "$0")" && pwd)"

usage() {
   cat << USAGE >&2
Usage:
   $cmdname [-h] [--help]

   -h
   --help
          Show this help message

    Docker login helper script

    Log into any docker registry configured with associated environment variables:
        "\${REGISTRY}_USERNAME"
        "\${REGISTRY}_API_KEY"
        "\${REGISTRY}_REPO"
USAGE
   exit 1
}


if [ "$1" = "-h" -o "$1" = "--help" ]; then
    usage
fi

. "$bin_path/utils.sh"

get_configured_registries | while read config ; do
    repo="$(echo "$config" | cut --delimiter ' ' --fields 1)"
    username="$(echo "$config" | cut --delimiter ' ' --fields 2)"
    api_key="$(echo "$config" | cut --delimiter ' ' --fields 3)"

    echo "Logging into $repo..."
    docker login \
        --username "$username" \
        --password "$api_key" \
    "$repo"
done
