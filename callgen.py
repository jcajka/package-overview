#!/usr/bin/python

# call-gen: gets random packages from koji
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

def gen():

    package = random.choice(PACKAGES)
    tag = random.choice(TAGS)
    logging.info("Getting: %s %s", package['package_name'], tag.name)
    try:
        _get_packageoverview(package['package_name'], tag.name)
        db.session.commit()
    except BaseException, e:
        db.session.rollback()
        raise e


if __name__ == '__main__':
    while True:
        time.sleep(random.choice(DELAY))
        try:
            gen()
        except Exception:
            logging.exception("Runtime exception")
