FROM debian:stretch as builder

ENV \
    ARTIFACT_DIR=/tmp/artifacts \
    DEBIAN_FRONTEND=noninteractive

# Install tools for reading build-time dependencies; see `Build-Depends`
# Squelch superfluous output; apt-get has poor verbosity control
RUN \
    apt-get update --quiet > /dev/null && \
    apt-get install --quiet --quiet --no-install-recommends \
        devscripts \
        equivs \
        git | grep "Setting up" | awk '{print $3 $4}' ORS=' '
        # only print package names, versions

WORKDIR /root/portal

# Copy repo into image
COPY . .

RUN \
    mk-build-deps debian/control \
        --install \
        --remove \
        --tool "apt-get --quiet --quiet --no-install-recommends"

# Generate changelog and build package
RUN \
    dpkg-buildpackage \
        --unsigned-source \
        --unsigned-changes \
        --hook-init=debian/pre-build.sh \
        --hook-done=debian/post-build.sh

# --------------------------------------

FROM debian:stretch

ENV \
    ARTIFACT_DIR=/tmp/artifacts \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    RUN_USER=www-data

# Install locally from $ARTIFACT_DIR by default
ARG debian_sources_entry="deb file:${ARTIFACT_DIR} ./"

RUN echo $debian_sources_entry > /etc/apt/sources.list.d/truenth-portal.list

COPY --from=builder "${ARTIFACT_DIR}" "${ARTIFACT_DIR}"

RUN \
    apt-get update --quiet > /dev/null && \
    apt-get install --quiet --quiet --allow-unauthenticated portal && \
    rm --force --recursive --verbose "${ARTIFACT_DIR}"

ENV \
    BASH_ENV=/etc/profile.d/remap_envvars.sh \
    FLASK_APP=/opt/venvs/portal/bin/manage.py \
    GUNICORN_CMD_ARGS='--timeout 90' \
    PORT=8008

USER "${RUN_USER}"

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
