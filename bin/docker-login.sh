#!/bin/sh -e

cmdname=$(basename $0)

usage() {
   cat << USAGE >&2
Usage:
   $cmdname [-h] [--help]

   -h
   --help
          Show this help message

    Docker helper script

    Log into any docker registry configured with associated environment variables:
        "\${REGISTRY}_USERNAME"
        "\${REGISTRY}_API_KEY"
        "\${REGISTRY}_REPO"
USAGE
   exit 1
}

if [ "$1" = "-h" -o "$1" = "--help" ]; then
    usage
    exit 0
fi

printenv | grep '_API_KEY' | cut --delimiter = --fields 1 | while read envvar_name; do
    delivery_target_name="$(echo $envvar_name | awk -F '_API_KEY' '{print $1; print $3}')"

    api_key="$(printenv "${delivery_target_name}_API_KEY" || true)"
    username="$(printenv "${delivery_target_name}_USERNAME" || true)"
    repo="$(printenv "${delivery_target_name}_REPO" || true)"

    if [ -n "$api_key" -a -n "$username" -a -n "$repo" ]; then
        echo docker login \
            --username "$username" \
            --password "$api_key" \
        "$repo"
    fi
done
