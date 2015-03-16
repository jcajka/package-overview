#!/usr/bin/python

# getallpackages: gets all packages in to the DB, using package list from koji
# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>
import koji
import random
import time
import logging

from statusweb import _get_packageoverview, db
from statusweb import Tag

TAGS = Tag.query.filter(Tag.active == True).all()
SESSION = koji.ClientSession("http://koji.fedoraproject.org/kojihub")
PACKAGES = SESSION.listPackages()
DELAY = range(5, 30)




def get(pname):

	for tag in TAGS:
            logging.info("Getting: %s %s", pname, tag.name)
            try:
                _get_packageoverview(pname, tag.name)
                db.session.commit()
            except BaseException, e:
                db.session.rollback()
                raise e


if __name__ == '__main__':
    for package in PACKAGES:
        try:
            get(package['package_name'])
        except Exception, e:
            logging.exception("Runtime exception")
            continue
