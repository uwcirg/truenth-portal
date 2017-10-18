#!/bin/sh -e
# Common functions for scripts

get_configured_registries() {
    # Read docker registry configuration from set of 3 environment variables and print to stdout

    printenv | grep '_REPO' | cut --delimiter = --fields 1 | while read envvar_name; do
        delivery_target_name="$(echo $envvar_name | awk -F '_REPO' '{print $1; print $3}')"

        # "${REGISTRY}_REPO" - registry domain or URL
        local repo="$(printenv "${delivery_target_name}_REPO" || true)"

        # "${REGISTRY}_USERNAME" - username used to log into docker registry
        local username="$(printenv "${delivery_target_name}_USERNAME" || true)"

        # "${REGISTRY}_API_KEY" - API key or password needed to authenticate with registry
        local api_key="$(printenv "${delivery_target_name}_API_KEY" || true)"

        if [ -n "$api_key" -a -n "$username" -a -n "$repo" ]; then
            # Print docker registry configuration, one line per configuration, space separated
            echo "$repo" "$username" "$api_key"
        fi
    done
}
