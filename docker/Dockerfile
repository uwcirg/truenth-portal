FROM debian:jessie

ENV DEBIAN_FRONTEND noninteractive

RUN \
    apt-get update && \
    apt-get dist-upgrade --yes && \
    apt-get install --yes --force-yes --no-install-recommends \
        apache2 \
        libapache2-mod-wsgi \
        libpq5 \
        python2.7 && \
    apt-get clean

RUN printf '\n\
Listen 0.0.0.0:${PORT}\n\
ServerName ${APACHE_SERVER_NAME}\n\
ErrorLog /dev/stdout\n\
<VirtualHost *:${PORT}>\n\
  LogLevel info\n\
  ErrorLog /dev/stdout\n\
  CustomLog /dev/stdout combined\n\
  WSGIPassAuthorization On\n\
  WSGIDaemonProcess stg_cs user=${APACHE_RUN_USER} group=${APACHE_RUN_GROUP} threads=5\n\
  WSGIScriptAlias / /var/www/portal.wsgi\n\
  <Directory /var/www/>\n\
    WSGIProcessGroup stg_cs\n\
    WSGIApplicationGroup %%{GLOBAL}\n\
    Require all granted\n\
  </Directory>\n\
</VirtualHost>\n\
\n'\
> /etc/apache2/sites-available/portal.conf

ARG debian_repo="http://dl.bintray.com/v1/content/uwcirg/truenth"

COPY artifacts /tmp/artifacts

# Only add local repository if packages available in artifacts/
RUN \
    if [ -n "$(ls -A /tmp/artifacts)" ]; then \
        echo deb file:/tmp/artifacts ./ > /etc/apt/sources.list.d/truenth.local.list; \
    else \
        echo deb ${debian_repo} stable main > /etc/apt/sources.list.d/truenth.list; \
    fi

RUN \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 379CE192D401AB61 && \
    apt-get update && \
    apt-get install --yes --force-yes portal && \
    apt-get clean && \
    rm --force --recursive --verbose /tmp/artifacts

COPY portal.wsgi /var/www/

ENV \
    APACHE_RUN_USER="${APACHE_RUN_USER:-www-data}" \
    LOG_FOLDER="/tmp/shared_service_log" \
    PORT="${PORT:-8008}" \
    PROJECT_DIR="/opt/venvs/portal"

RUN \
    mkdir -p ${LOG_FOLDER} ${PROJECT_DIR}/var/portal-instance/ && \
    chown $APACHE_RUN_USER:$APACHE_RUN_USER \
        /var/run/apache2/ \
        ${LOG_FOLDER} \
        ${PROJECT_DIR}/var/portal-instance/ && \
    sed -i 's|Listen [[:digit:]]\+|Listen ${PORT}|g' /etc/apache2/ports.conf && \
    a2ensite portal && a2dissite 000-default && a2disconf other-vhosts-access-log

USER ${APACHE_RUN_USER}

ENV \
    APACHE_SERVER_NAME=${APACHE_SERVER_NAME:-localhost} \
    FLASK_APP="${PROJECT_DIR}/bin/manage.py" \
    PERSISTENCE_FILE="${PERSISTENCE_FILE:-https://raw.githubusercontent.com/uwcirg/TrueNTH-USA-site-config/develop/site_persistence_file.json}"

EXPOSE ${PORT}

CMD \
    . /etc/apache2/envvars && \
    . ${PROJECT_DIR}/bin/activate && \
    env && \
    if [ -n "$(flask db current)" ]; then \
        flask db migrate; \
    else \
        python ${FLASK_APP} initdb; \
    fi && \
    /usr/sbin/apache2 -D FOREGROUND
