Contributing
************

.. contents::
   :depth: 3
   :local:

Git Flow Workflow
=================

TrueNTH Shared Services attempts to conform to the guidelines established
by the git-flow branching model.

For an introduction, see the excellent `git-flow-cheatsheet <http://danielkummer.github.io/git-flow-cheatsheet/>`_.

To initialize on a debian system, install the git-flow package::

    sudo apt-get install git-flow

Return to the root of your TrueNTH Shared Services checkout and initialize::

    cd ~/truenth-portal
    git-flow init

You should be able to accept all the defaults (caveat: in some cases "Branch name for production releases: []" won't have a default; in that case, use "master").  The results are written to the nested `.git/config` file, such as::

    [gitflow "branch"]
            master = master
            develop = develop
    [gitflow "prefix"]
            feature = feature/
            release = release/
            hotfix = hotfix/
            support = support/
            versiontag = 

Work on New Feature
===================

Work on new feature takes place in a fresh branch off of develop.  **git-flow**
makes this easy::

    git flow feature start my-feature-name

Publish Feature
===============

Once the feature is ready to share, and all changes have been committed
locally, push the feature branch to github::

    git flow feature publish

Pull Request
============

To bring the feature into the main develop branch, head over to
`github <https://github.com/uwcirg/truenth-portal>`_ and trigger
a **pull request**.

Rebase
======

Occasionally, it's desirable or even necessary to bring commits on another
branch into your feature branch prior to publication.

For example, to bring changes into your branch that have been pushed
to `develop` since your feature branch was cut::


    git checkout develop
    git pull
    git checkout feature/<my-feature-name>
    git flow feature rebase
