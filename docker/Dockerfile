FROM debian:jessie

ENV \
    DEBIAN_FRONTEND="noninteractive"

RUN \
    apt-get update && \
    apt-get dist-upgrade --yes && \
    apt-get install --yes --force-yes --no-install-recommends \
        libpq5 \
        python2.7 && \
    apt-get clean

ARG debian_repo="http://dl.bintray.com/v1/content/uwcirg/truenth"

COPY artifacts /tmp/artifacts

# Only add local repository if packages available in artifacts/
RUN \
    if [ -n "$(ls -A /tmp/artifacts)" ]; then \
        echo deb file:/tmp/artifacts ./ > /etc/apt/sources.list.d/truenth.local.list; \
    else \
        echo deb "${debian_repo}" stable main > /etc/apt/sources.list.d/truenth.list; \
    fi

RUN \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 379CE192D401AB61 && \
    apt-get update && \
    apt-get install --yes --force-yes portal && \
    apt-get clean && \
    rm --force --recursive --verbose /tmp/artifacts

ENV \
    RUN_USER="${RUN_USER:-www-data}" \
    PROJECT_DIR="/opt/venvs/portal"

RUN \
    mkdir --parents "${PROJECT_DIR}/var/portal-instance/" && \
    chown "$RUN_USER:$RUN_USER" "${PROJECT_DIR}/var/portal-instance/"

USER "${RUN_USER}"

ENV \
    SERVER_NAME="${SERVER_NAME:-localhost}" \
    PORT="${PORT:-8008}" \
    FLASK_APP="${PROJECT_DIR}/bin/manage.py" \
    PERSISTENCE_FILE="${PERSISTENCE_FILE:-https://raw.githubusercontent.com/uwcirg/TrueNTH-USA-site-config/develop/site_persistence_file.json}"

EXPOSE "${PORT}"

CMD \
    . "${PROJECT_DIR}/bin/activate" && \
    eval $("${PROJECT_DIR}/bin/remap_envvars.py") && \
    env && \
    flask sync && \
    gunicorn \
        --bind "0.0.0.0:${PORT}" \
        `# Workaround to gunicorn sync workers bug` \
        `# https://github.com/benoitc/gunicorn/issues/1194` \
        --timeout 90 \
        --keep-alive 75 \
    manage:app
