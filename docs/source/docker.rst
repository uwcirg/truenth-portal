Docker
************

.. contents::
   :depth: 3
   :local:

Background
==========

Docker is an open-source project that automates the deployment of applications inside software containers. Docker defines specifications and provides tools that can be used to automate building and deploying software containers.

Dockerfiles declaratively define how to build a Docker :term:`image` that is subsequently run as a :term:`container`, any number of times. Configuration in Dockerfiles is primarily driven by image build-time arguments (ARG) and environment variables (ENV) that may be overridden.

Docker-compose (through docker-compose.yaml) defines the relationship (exposed ports, volume mapping) between the Shared Services web container and the other services it depends on (redis, postgresql).

Getting Started
===============
Install `docker-compose` as per environment.  For example, from a debian system::

    sudo usermod -aG docker $USER # add user to docker group
    sudo pip install docker_compose

Copy and edit the default environment file (from the project root)::

    cp docker/portal.env.default docker/portal.env
    # update SERVER_NAME to include port if not binding with 80/443
    # SERVER_NAME=localhost:8080

Download and run the generated images::

    COMPOSE_FILE='docker/docker-compose.yaml'
    docker-compose up web

By default, the ``portal_web`` image with the ``latest`` tag is downloaded and used. To use another tag, set the ``IMAGE_TAG`` environment variable::

    IMAGE_TAG='stable'
    COMPOSE_FILE='docker/docker-compose.yaml'
    docker-compose up web


Docker Images
=============

Two Dockerfiles (Dockerfile.build and Dockerfile) define how to build docker images capable of creating a Debian package from the portal codebase, and how to install and configure the package into a working Shared Services instance.

Building a Debian Package
-------------------------

To build a Debian package from your local ``develop`` branch::

    # Build debian package from local develop branch
    COMPOSE_FILE='docker/docker-compose.yaml:docker/docker-compose.build.yaml'
    docker-compose run builder

.. note::
    All of these commands are run from the git top level directory (obtained by:``git rev-parse --show-toplevel``)

If you would like to create a package from a topic branch or fork you can override the local repo and branch as below::

    COMPOSE_FILE='docker/docker-compose.yaml:docker/docker-compose.build.yaml'

    # Override defaults with environment variables
    BRANCH='feature/feature-branch-name'
    GIT_REPO='https://github.com/USERNAME/true_nth_usa_portal'

    # Run the container (override defaults)
    docker-compose run builder

.. note::
    The branch specified must exist on Github

Building a Shared Services Docker Image
---------------------------------------


If you would like to build a Shared Services container against a topic branch on Github, follow the instructions in `Building a Debian Package`_, and run the following docker-compose commands::

    # Override default (Artifactory) docker repo to differentiate locally-built images
    REPO='local'

    # Build the "web" service locally
    COMPOSE_FILE='docker/docker-compose.yaml'
    docker-compose build web

    docker-compose up web

PostgreSQL Access
-----------------
To interact with the database image started via the ``docker-compose`` instructions above, use ``docker exec`` such as::

    docker-compose exec db psql --username postgres

Advanced Configuration
======================

Environment variables defined in the ``portal.env`` environment file are only passed to the underlying "web" container. However, some environment variables are used for configuration specific to docker-compose.

An
`additional environment file <https://docs.docker.com/compose/environment-variables/#the-env-file>`__, specifically named ``.env``, in current working directory can define environment variables available through the entire docker-compose file (including containers). These docker-compose-level environment variables can also be set in the shell invoking docker-compose.

One use for these more "global" environmental variables is overriding the default ``COMPOSE_PROJECT_NAME`` which is used to namespace applications running under docker-compose. In production deployments ``COMPOSE_PROJECT_NAME`` is set to correspond to the domain being served.

Continuous Delivery
===================

Our continuous integration setup leverages TravisCI's docker support and deployment integration to create and deploy Debian packages and Docker images for every commit.

Packages and images are built in a separate :term:`job` (named "build") that corresponds with a tox environment that does nothing and that's allowed to fail without delaying the build or affecting its status.

If credentials are configured, packages and images will be uploaded to their corresponding repository after the build process. Otherwise, artifacts will only be built, but not uploaded or deployed.

Currently, our TravisCI setup uses packages locally-built on TravisCI instead of pushing, then pulling from our Debian repository. This may lead to non-deterministic builds and should probably be reconciled at some point.

Configuration
-------------

Most if not all values needed to build and deploy Shared Services are available as environment variables with sane, CIRG-specific defaults. Please see the `global section of .travis.yml <https://docs.travis-ci.com/user/environment-variables#global-variables>`_.

.. glossary::

    image
        Docker images are the basis of containers. An Image is an ordered collection of root filesystem changes and the corresponding execution parameters for use within a container runtime. An image typically contains a union of layered filesystems stacked on top of each other. An image does not have state and it never changes.

    container
        A container is a runtime instance of a docker image.
        A Docker container consists of:
        * A Docker image
        * Execution environment
        * A standard set of instructions

    environment file
        A file for defining environment variables. One per line, no shell syntax (export etc).

    build
        A group of TravisCI jobs tied to a single commit; initiated by a pull request or push

    job
        A discrete unit of work that is part of a build. All jobs part of a build must pass for the build to pass (unless a job is set as an `allowed failure <https://docs.travis-ci.com/user/customizing-the-build#rows-that-are-allowed-to-fail>`_).

