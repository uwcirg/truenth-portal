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

ENV PROJECT_DIR="/opt/venvs/portal"
ENV \
    FLASK_APP="${PROJECT_DIR}/bin/manage.py" \
    LOG_FOLDER="/tmp/shared_service_log" \
    PERSISTENCE_FILE="https://raw.githubusercontent.com/uwcirg/TrueNTH-USA-site-config/master/site_persistence_file.json" \
    SQLALCHEMY_DATABASE_URI="postgresql://postgres:@db/postgres" \
    CELERY_BROKER_URL="redis://redis:6379/0" \
    REQUEST_CACHE_URL="redis://redis:6379/0" \
    SESSION_REDIS_URL="redis://redis:6379/0"
RUN mkdir -p ${LOG_FOLDER} ${PROJECT_DIR}/var/portal-instance/
RUN chown www-data:www-data ${LOG_FOLDER} ${PROJECT_DIR}/var/portal-instance/

COPY portal.wsgi /var/www/
COPY portal.conf /etc/apache2/sites-available
RUN a2ensite portal

EXPOSE 80

CMD \
    . /etc/apache2/envvars && \
    . ${PROJECT_DIR}/bin/activate && \
    ${FLASK_APP} initdb && \
    /usr/sbin/apache2 -D FOREGROUND
