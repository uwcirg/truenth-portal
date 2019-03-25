#!/bin/sh -e
# Common functions for scripts

get_configured_registries() {
    # Read docker registry configuration from set of 3 environment variables and print to stdout

    printenv | cut --delimiter = --fields 1 | grep '_REPO$' | while read envvar_name; do
        delivery_target_name="$(echo $envvar_name | awk -F '_REPO' '{print $1}')"

        # "${REGISTRY}_REPO" - registry domain or URL
        local repo="$(printenv "${delivery_target_name}_REPO" || true)"

        # "${REGISTRY}_USERNAME" - username used to log into docker registry
        local username="$(printenv "${delivery_target_name}_USERNAME" || true)"

        # "${REGISTRY}_API_KEY" - API key or password needed to authenticate with registry
        local api_key="$(printenv "${delivery_target_name}_API_KEY" || true)"

        if [ -n "$api_key" ] && [ -n "$username" ] && [ -n "$repo" ]; then
            # Print docker registry configuration, one line per configuration, space separated
            echo "$repo" "$username" "$api_key"
        fi
    done
}


get_docker_tags() {
    # Build newline-separated list of tags for tagging docker images from available information

    GIT_BRANCH="${GIT_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
    # Standardize branch name
    if [ "$GIT_BRANCH" = "develop" ]; then
        GIT_BRANCH="latest"
    fi
    if [ "$GIT_BRANCH" = "master" ]; then
        GIT_BRANCH="stable"
    fi
    GIT_BRANCH="$(echo $GIT_BRANCH | tr / _)"
    GIT_TAG="${GIT_TAG:-$(git describe --tags --exact-match 2>/dev/null || true)}"
    GIT_HASH="${GIT_HASH:-$(git rev-parse HEAD)}"
    GIT_SHORT_HASH="${GIT_SHORT_HASH:-$(git rev-parse --short HEAD)}"

    DOCKER_TAGS=$(cat << BLOCK
$GIT_BRANCH
$GIT_TAG
$GIT_HASH
$GIT_SHORT_HASH
$DOCKER_EXTRA_TAGS
BLOCK
)
    # Remove extra newlines
    DOCKER_TAGS="$(echo "$DOCKER_TAGS" | tr --squeeze-repeats '\n' '\n')"

    echo "$DOCKER_TAGS"
}
