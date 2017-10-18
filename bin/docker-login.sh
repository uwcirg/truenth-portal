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

get_configured_registries() {
    # Read docker registry configuration from set of 3 environment variables and print to stdout

    printenv | grep '_REPO' | cut --delimiter = --fields 1 | while read envvar_name; do
        delivery_target_name="$(echo $envvar_name | awk -F '_REPO' '{print $1; print $3}')"

        # "${REGISTRY}_API_KEY" - API key or password needed to authenticate with registry
        local api_key="$(printenv "${delivery_target_name}_API_KEY" || true)"

        # "${REGISTRY}_USERNAME" - username used to log into docker registry
        local username="$(printenv "${delivery_target_name}_USERNAME" || true)"

        # "${REGISTRY}_REPO" - registry domain or URL
        local repo="$(printenv "${delivery_target_name}_REPO" || true)"

        if [ -n "$api_key" -a -n "$username" -a -n "$repo" ]; then
            # Print docker registry configuration, one line per configuration, space separated
            echo "$repo" "$username" "$api_key"
        fi
    done
}

get_configured_registries | while read config ; do
   read repo username api_key <<< "$config"

    echo docker login \
        --username "$username" \
        --password "$api_key" \
    "$repo"

done
