Docker
************

.. contents::
   :depth: 3
   :local:

Background
==========

Docker is an open-source project that automates the deployment of applications inside software containers. Docker defines specifications and provides tools that can be used to automate building and deploying software containers.

Dockerfiles declaratively define how to build a Docker :term:`image` that is subsequently run as a :term:`container`, any number of times. Configuration in Dockerfiles is primarily driven by image build-time arguments (ARG) and environmental variables (ENV) that may be overridden.

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

Containers
==========

Two Dockerfiles (Dockerfile.build and Dockerfile) define how to build a Debian package from the portal codebase and how to install and configure the package into a working Shared Services instance.

Building a Debian Package
-------------------------

To build a Debian package from your current ``develop``::

    # Build debian package from local develop branch
    COMPOSE_FILE='docker/docker-compose.yaml:docker/docker-compose.build.yaml'
    docker-compose run builder


.. note::
    All of these commands are run from the git top level directory (obtained by:``git rev-parse --show-toplevel``)

If you would like to create a package from a topic branch or fork you can override the local repo and branch as below::

    # Override defaults with environmental variables
    REPO='USERNAME/true_nth_usa_portal'
    BRANCH='feature/feature-branch-name' COMPOSE_FILE='docker/docker-compose.yaml:docker/docker-compose.build.yaml'

    # Run the container (override defaults)
    docker-compose run builder

.. note::
    The branch specified must exist on Github

Orchestration
-------------
Docker-compose (through docker-compose.yaml) defines the relationship (exposed ports, volume mapping) between the Shared Services web container and the other services it depends on (redis, postgresql).

Docker-compose offers a higher-level interface to build and run containers together but may be supplanted by Docker stacks in the future.

To download and start the set of containers that comprise Shared Services issue the following command::

    # Download and start web container and dependencies
    COMPOSE_FILE='docker/docker-compose.yaml'
    docker-compose up web

By default, the ``portal_web`` image with the ``latest`` tag is downloaded and used. To use another tag, set the ``IMAGE_TAG`` environmental variable::

    IMAGE_TAG='stable'
    COMPOSE_FILE='docker/docker-compose.yaml'
    docker-compose up web

If you would like to build a Shared Services container against a topic branch on Github, follow the instructions in `Building a Debian Package`_, and run the following docker-compose commands::

    # Build the "web" service locally instead of downloading from a docker registry
    COMPOSE_FILE='docker/docker-compose.yaml:docker/docker-compose.build.yaml'
    docker-compose build web

    # Disable remote repo so locally-built image is used
    REPO='' docker-compose up web

PostgreSQL Access
-----------------
To interact with the database image started via the ``docker-compose`` instructions above, use ``docker exec`` such as::

    docker exec -it docker_db_1 /usr/lib/postgresql/9.6/bin/psql -U postgres

Continuous Delivery
===================

Our continuous integration setup leverages TravisCI's docker support and deployment integration to create and deploy Debian packages and Docker images for every commit.

Packages and images are built in a separate :term:`job` (named "build") that corresponds with a tox environment that does nothing and that's allowed to fail without delaying the build or affecting its status.

If credentials are configured, packages and images will be uploaded to their corresponding repository after the build process. Otherwise, artifacts will only be built, but not uploaded or deployed.

Currently, our TravisCI setup uses packages locally-built on TravisCI instead of pushing, then pulling from our Debian repository. This may lead to non-deterministic builds and should probably be reconciled at some point.

Configuration
-------------

Most if not all values needed to build and deploy Shared Services are available as environmental variables with sane, CIRG-specific defaults. Please see the `global section of .travis.yml <https://docs.travis-ci.com/user/environment-variables#global-variables>`_.

.. glossary::

    image
        Docker images are the basis of containers. An Image is an ordered collection of root filesystem changes and the corresponding execution parameters for use within a container runtime. An image typically contains a union of layered filesystems stacked on top of each other. An image does not have state and it never changes.

    container
        A container is a runtime instance of a docker image.
        A Docker container consists of:
        * A Docker image
        * Execution environment
        * A standard set of instructions

    build
        A group of TravisCI jobs tied to a single commit; initiated by a pull request or push

    job
        A discrete unit of work that is part of a build. All jobs part of a build must pass for the build to pass (unless a job is set as an `allowed failure <https://docs.travis-ci.com/user/customizing-the-build#rows-that-are-allowed-to-fail>`_).

