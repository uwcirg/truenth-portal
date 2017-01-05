FROM debian:jessie

ENV DEBIAN_FRONTEND noninteractive

RUN echo deb http://dl.bintray.com/v1/content/ivan-c/true_nth stable main > /etc/apt/sources.list.d/truenth.list

RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 379CE192D401AB61

RUN apt-get clean && apt-get update && apt-get -y dist-upgrade && apt-get -y --force-yes install \
	apache2 \
	libapache2-mod-wsgi \
	locales \
	portal \
	postgresql \
	python2.7

RUN dpkg-reconfigure locales && \
    locale-gen C.UTF-8 && \
    /usr/sbin/update-locale LANG=C.UTF-8

ENV \
    APACHE_LOCK_DIR="/var/lock/apache2" \
    APACHE_LOG_DIR="/var/log/apache2" \
    APACHE_PID_FILE="/var/run/apache2.pid" \
    APACHE_RUN_GROUP="www-data" \
    APACHE_RUN_USER="www-data"

ENV APACHE_CONFDIR /etc/apache2
ENV APACHE_ENVVARS $APACHE_CONFDIR/envvars

RUN set -ex && \
    . "$APACHE_ENVVARS" && \
    for dir in "$APACHE_LOCK_DIR" "$APACHE_RUN_DIR" "$APACHE_LOG_DIR" /var/www/html ; do \
        rm -rvf "$dir" && \
        mkdir -p "$dir" && \
        chown -R "$APACHE_RUN_USER:$APACHE_RUN_GROUP" "$dir"; \
    done

RUN mkdir -p /tmp/shared_service_log
ENV \
    PROJECT_DIR="/opt/venvs/portal" \
    LOG_FOLDER="/tmp/shared_service_log" \
    PERSISTENCE_FILE="https://raw.githubusercontent.com/uwcirg/TrueNTH-USA-site-config/da53ab8e627f850e44af31cad169826b2bbcbb49/site_persistence_file.json" \
    SQLALCHEMY_DATABASE_URI="postgresql://postgres:5s480OFh@172.17.0.2/postgres" \
    CELERY_BROKER_URL="redis://172.17.0.3:6379/0" \
    SESSION_REDIS="172.17.0.3:6379"
COPY portal.wsgi /var/www/
COPY portal.conf /etc/apache2/sites-available
COPY manage.py ${PROJECT_DIR}/bin
RUN a2ensite portal

RUN ${PROJECT_DIR}/bin/python ${PROJECT_DIR}/bin/manage.py initdb

EXPOSE 80

CMD . /etc/apache2/envvars && /usr/sbin/apache2 -D FOREGROUND
