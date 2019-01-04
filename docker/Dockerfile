FROM debian:stretch

ENV \
    ARTIFACT_DIR=/tmp/artifacts \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

RUN \
    apt-get update --quiet && \
    apt-get dist-upgrade --quiet --quiet && \
    apt-get install --quiet --quiet --no-install-recommends \
        ca-certificates \
        libpq5 \
        python2.7 \
        wait-for-it && \
    apt-get clean --quiet

ARG debian_repo="https://uwcirg.jfrog.io/uwcirg/portal-deb"

COPY debian/artifacts "${ARTIFACT_DIR}"

# Only add local repository if packages available in artifacts/
RUN \
    if [ -n "$(ls ${ARTIFACT_DIR})" ]; then \
        echo "deb file:${ARTIFACT_DIR}" ./ > /etc/apt/sources.list.d/truenth.local.list; \
    else \
        echo deb "${debian_repo}" stable main > /etc/apt/sources.list.d/truenth.list; \
    fi

RUN \
    apt-get update --quiet && \
    apt-get install --quiet --quiet --allow-unauthenticated portal && \
    apt-get clean --quiet && \
    rm --force --recursive --verbose "${ARTIFACT_DIR}"

ENV \
    BASH_ENV="/etc/profile.d/remap_envvars.sh" \
    FILE_UPLOAD_DIR="${FILE_UPLOAD_DIR:-/var/lib/portal/uploads}" \
    PERSISTENCE_EXCLUSIONS_DIR="${PERSISTENCE_EXCLUSIONS_DIR:-/var/tmp/exclusions}" \
    PROJECT_DIR="/opt/venvs/portal" \
    RUN_USER="${RUN_USER:-www-data}"

# Todo: move to debian package postinst script
RUN \
    mkdir --parents \
        "${FILE_UPLOAD_DIR}" \
        "${PERSISTENCE_EXCLUSIONS_DIR}" \
        "${PROJECT_DIR}/var/portal-instance/" && \
    chown "$RUN_USER:$RUN_USER" \
        "${FILE_UPLOAD_DIR}" \
        "${PERSISTENCE_EXCLUSIONS_DIR}" \
        "${PROJECT_DIR}/var/portal-instance/" && \
    echo 'eval $("${PROJECT_DIR}/bin/remap_envvars.py")' > /etc/profile.d/remap_envvars.sh


USER "${RUN_USER}"
SHELL ["/bin/bash", "-c"]

ENV \
    SERVER_NAME="${SERVER_NAME:-localhost}" \
    PORT="${PORT:-8008}" \
    FLASK_APP="${PROJECT_DIR}/bin/manage.py" \
    PATH="${PROJECT_DIR}/bin:${PATH}" \
    PERSISTENCE_DIR="${PERSISTENCE_DIR:-gil}" \
    TIMEOUT="${TIMEOUT:-90}"

EXPOSE "${PORT}"

CMD \
    env && \

    wait-for-it \
        --host="$PGHOST" \
        --port="$PGPORT" \
        --strict \
    -- \

        flask sync && \

        gunicorn \
            --bind "0.0.0.0:${PORT}" \
            --timeout ${TIMEOUT} \
        wsgi:application
