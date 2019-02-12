FROM debian:stretch

ENV \
    ARTIFACT_DIR=/tmp/artifacts \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

# Install locally from $ARTIFACT_DIR by default
ARG debian_sources_entry="deb file:${ARTIFACT_DIR} ./"

RUN echo $debian_sources_entry > /etc/apt/sources.list.d/truenth-portal.list

COPY debian/artifacts "${ARTIFACT_DIR}"

ENV \
    FILE_UPLOAD_DIR=/var/lib/portal/uploads \
    PERSISTENCE_EXCLUSIONS_DIR=/var/tmp/exclusions \
    RUN_USER=www-data

RUN \
    apt-get update --quiet && \
    apt-get install --quiet --quiet --allow-unauthenticated portal && \
    apt-get clean --quiet && \
    rm --force --recursive --verbose "${ARTIFACT_DIR}"

USER "${RUN_USER}"

ENV \
    BASH_ENV=/etc/profile.d/remap_envvars.sh \
    FLASK_APP=/opt/venvs/portal/bin/manage.py \
    GUNICORN_CMD_ARGS='--timeout 90' \
    PORT=8008

EXPOSE "${PORT}"

CMD \
    wait-for-it \
        --host="${PGHOST}" \
        --port="${PGPORT:-5432}" \
        --strict \
    -- \

        flask sync && \

        gunicorn \
            --bind "0.0.0.0:${PORT}" \
        wsgi:application
