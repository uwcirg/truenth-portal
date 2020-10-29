FROM node:12 as substudy_app

RUN mkdir /tmp/substudy_app
WORKDIR /tmp/substudy_app

# Copy required front-end files only
COPY  portal/eproms_substudy_tailored_content/  ./

RUN npm install

RUN npm run build
# -----------------------------------------------------------------------------


FROM debian:buster as builder

ENV \
    ARTIFACT_DIR=/tmp/artifacts \
    DEBIAN_FRONTEND=noninteractive

# Install tools for reading build dependencies; see `Build-Depends`
# Squelch superfluous output; apt-get has poor verbosity control
RUN \
    apt-get update --quiet > /dev/null && \
    apt-get install --quiet --quiet --no-install-recommends \
        devscripts \
        equivs \
        git | grep "Setting up" | awk '{print $3 $4}' ORS=' '
        # only print package names, versions

WORKDIR "$HOME/portal"

# Copy repo into image
COPY . .


# Install build dependencies
RUN \
    mk-build-deps debian/control \
        --install \
        --remove \
        --tool "apt-get --quiet --quiet --no-install-recommends"

# Generate changelog, build package and move package files to ARTIFACT_DIR
RUN \
    dpkg-buildpackage \
        --unsigned-source \
        --unsigned-changes \
        --hook-init=debian/pre-build.sh \
        --hook-done=debian/post-build.sh

# -----------------------------------------------------------------------------

FROM debian:buster as production

ENV \
    ARTIFACT_DIR=/tmp/artifacts \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    RUN_USER=www-data

# Install locally from $ARTIFACT_DIR by default
ARG debian_sources_entry="deb [trusted=yes] file:${ARTIFACT_DIR} ./"

RUN echo $debian_sources_entry > /etc/apt/sources.list.d/truenth-portal.list

# Copy package files from previous stage
COPY --from=builder "${ARTIFACT_DIR}" "${ARTIFACT_DIR}"

RUN \
    apt-get update --quiet > /dev/null && \
    apt-get install --quiet --quiet portal && \
    rm --force --recursive --verbose "${ARTIFACT_DIR}"

# Copy substudy app files built in substudy_app stage
COPY --from=substudy_app /tmp/substudy_app/dist/bundle/ /opt/venvs/portal/lib/python3.7/site-packages/portal/static/bundle/
COPY --from=substudy_app /tmp/substudy_app/dist/templates/ /opt/venvs/portal/lib/python3.7/site-packages/portal/static/templates/

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
