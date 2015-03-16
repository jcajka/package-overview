#!/usr/bin/python

# coherencetest: check random packages overview from db with overview from koji and reports differences
# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>

from packagestatus import get_packageoverview

from statusweb import _get_packageoverview, db, Package
from statusweb import Tag

from dbtest import equalbs

from datetime import datetime

import random
import logging
import time
import sys

def testcoherence(pkgs=None):

    ch = None

    if not pkgs:
        packages = Package.query.all()

        random.jumpahead(9999)

        if not packages: 
            return

        ch = random.sample(packages, 100 if len(packages) > 100 else len(packages))

    else:

        ch = []

        for pkg in pkgs:
            
            ch.append( Package.query.filter(Package.name == pkg).one())
            
    
    logging.info("--------------")
    for p in ch:
        logging.info("%s", p.name)
    logging.info("--------------")
    tags = Tag.query.filter(Tag.active == True).all()
    
    miss = {}

    for tag in tags:
        miss[tag.name] = []

    for package in ch:
        for tag in tags:
            pkoji = get_packageoverview(package.name, tag.name)
            try:
                pdb = _get_packageoverview(package.name, tag.name)
                db.session.commit()
            except BaseException, e:
                db.session.rollback()
                raise e
            if not pkoji, or not pdb:
                miss[tag.name].append((package.name,[pkoji,pdb]))
            else:            
                diff = equalbs(pkoji, pdb)
            if diff:
                miss[tag.name].append((package.name, diff))
                logging.warn("Missmatching builds\n%s", diff)
        
    logging.info("--------------")
    logging.info("Missmatching results:")
    for tag in tags:
        logging.info("Tag: %s", tag.name)
        for i in miss[tag.name]:
            for f in i:
                logging.info("%s", f)
    logging.info("--------------")


if __name__ == '__main__':
    while True:
        logging.info("Starting test %s", datetime.now())
        try:
            if len(sys.argv) > 1:
                testcoherence(pkgs=sys.argv[1:])
            else:
                testcoherence()
            db.session.close()
        except Exception, e:
            logging.exception("Runtime exception")
        logging.info("Finished test %s", datetime.now())
        if len(sys.argv) > 1:
            break
        time.sleep(1800)
