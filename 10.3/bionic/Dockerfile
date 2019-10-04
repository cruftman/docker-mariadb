#############################################################################
# NOTE: FILE GENERATED AUTOMATICALLY, DO NOT EDIT!!!
#############################################################################


# Based on:
# https://github.com/lindycoder/prepopulated-mysql-container-example
FROM mariadb:10.3-bionic as builder

ARG MYSQL_ROOT_PASSWORD='cruftman'
ARG MYSQL_DATABASE='cruftman'
ARG MYSQL_USER='cruftman'
ARG MYSQL_PASSWORD='cruftman'

ENV MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD \
    MYSQL_DATABASE=$MYSQL_DATABASE \
    MYSQL_USER=$MYSQL_USER \
    MYSQL_PASSWORD=$MYSQL_PASSWORD

# 1. docker-entrypoint.sh does the DB initialization but also runs mysql
#     daemon; By removing the last line it will only init.
# 2. Need to change the datadir to something else that /var/lib/mysql because
#    the parent docker file defines it as a volume.
#    https://docs.docker.com/engine/reference/builder/#volume :
#    Changing the volume from within the Dockerfile: If any build steps change
#    the data within the volume after it has been declared, those changes will
#    be discarded.
RUN sed -i 's/exec "$@"/echo not running "$@"/' /usr/local/bin/docker-entrypoint.sh && \
    /usr/local/bin/docker-entrypoint.sh mysqld --datadir /initialized-db --aria-log-dir-path /initialized-db

FROM mariadb:10.3-bionic
MAINTAINER Paweł Tomulik <ptomulik@meil.pw.edu.pl>



ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

LABEL org.label-schema.build-date="${BUILD_DATE}" \
      org.label-schema.name="Docker MariaDB Image" \
      org.label-schema.description="Docker image with MariaDB for Cruftman project." \
      org.label-schema.vcs-ref="${VCS_REF}" \
      org.label-schema.vcs-url="https://github.com/cruftman/docker-mariadb" \
      org.label-schema.vendor="Paweł Tomulik" \
      org.label-schema.version="${VERSION}" \
      org.label-schema.schema-version="1.0"



COPY --from=builder /initialized-db /var/lib/mysql

# vim: set ft=dockerfile:
