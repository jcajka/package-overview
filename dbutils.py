#!/usr/bin/python

# dbutils: utility to manipulate build entries in db
# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>

from statusweb import Tag, Build, Package, Koji, db, _get_packageoverview
from packagestatus import get_packageoverview
from dbtest import equalbs
import json
import datetime
import logging
import koji as _koji
import re

def tagbuild(bid, koji, tag):

    logging.debug("Getting build %s from %s to tag %s",
                  bid,
                  koji.name,
                  tag.name)
    build = Build.query.filter(Build.koji_id == koji.id,
                               Build.bid == int(bid)).one()
    assert build
    logging.debug("Tagged in to %s", tag.name)
    build.tags.append(tag)
    db.session.merge(build)
    db.session.commit()

def untagbuild(bid, koji, tag):

    logging.debug("Getting build %s from %s to tag %s",
                  bid,
                  koji.name,
                  tag.name)
    build = Build.query.filter(koji.id == Build.koji_id,
                               int(bid) == Build.bid).one()
    assert build
    build.tags = filter(lambda x: x.id != tag.id, build.tags)
    logging.debug("Untagged from %s", tag.name)
    db.session.merge(build)
    db.session.commit()

def update(package, tag):

    kojibs = get_packageoverview(package, tag)

    dbbs = _get_packageoverview(package, tag)

    logging.debug("Retrieved builds.")

    diff = equalbs(kojibs, dbbs)

    for k in diff:

        if diff[k][0]['build_id'] == diff[k][1]['build_id']:

            logging.debug("Updating build %s from %s",
                          diff[k][0]['build_id'],
                          k)
            kj = Koji.query.filter(Koji.name == k).one()

            tg = Tag.query.filter(Tag.name == tag).one()

            bs = Build.query.filter(Build.bid == diff[k][0]['build_id'],
                                    Build.koji_id == kj.id).one()

            if 'tagged' in diff[k][0]:

                if diff[k][0]['tagged']:

                    tagbuild(diff[k][0], kj, tg)

                del diff[k][0]['tagged']

            bs.build = json.dumps(diff[k][0])
            bs.fdate = datetime.datetime.strptime(diff[k][0]["creation_time"],
                                                  "%Y-%m-%d %H:%M:%S.%f")

            db.session.merge(bs)

        else:

            logging.debug("Skipping missmatching builds %s %s from %s",
                          diff[k][0]['build_id'],
                          diff[k][1]['build_id'],
                          k)

            continue

    db.session.commit()

def getbuild(bid, koji):

    kj = Koji.query.filter(Koji.name == koji).one()

    kjs = _koji.ClientSession(kj.getURL())

    bs = kjs.getBuild(bid)

    package = Package.query.filter(Package.name == bs['package_name']).first()

    if not package:

        #create new package and get basic overview
        tags = Tag.query.filter(Tag.active == True).all()
        for tag in tags:
            _get_packageoverview(bs['package_name'], tag.name)
            db.session.commit()

    print bs['release']
    mtch = re.match(".*fc(?P<rel>\d*).*", bs['release'])
    if mtch:
        rel = int(mtch.group("rel"))
    else:
        logging.warn("Couldn't determine rel from %s", bs['release'])
        rel = 9999

    bs['build_id'] = bs['id']

    build = Build(json.dumps(bs),
                  bs['id'],
                  package.id,
                  rel,
                  datetime.datetime.strptime(bs["creation_time"],
                                             "%Y-%m-%d %H:%M:%S.%f"))
    build.version = bs['version']
    build.release = bs['release']
    build.epoch = bs['epoch'] if bs['epoch'] else '0'
    build.state = bs['state']

    build.koji_id = kj.id

    db.session.merge(build)
    db.session.commit()
    return build

def delbuild(bid, koji):

    kj = Koji.query.filter(Koji.name == koji).one()

    build = Build.query.filter(Build.bid == bid, Build.koji_id == kj.id).one()

    db.session.delete(build)

    db.session.commit()

def dbfixup():

    builds = Build.query.all()

    for build in builds:
        bs = json.loads(build.build)
        if build.state != bs['state']:
            print "Fixing build %s state"%build.bid
            build.state = bs['state']
        if build.epoch != bs['epoch']:
            print "Fixing build %s epoch"%build.bid
            build.epoch = bs['epoch']
        if build.version != bs['version']:
            print "Fixing build %s version"%build.bid
            build.version = bs['version']
        if build.release != bs['release']:
            print "Fixing build %s release"%build.bid
            build.release = bs['release']
        db.session.merge(build)
    db.session.commit()



if __name__ == "__main__":


    import sys

    assert len(sys.argv) > 2

    if sys.argv[1] == "tagbuild":

        assert len(sys.argv) == 5

        bkoji = Koji.query.filter(Koji.name == sys.argv[2]).one()

        btag = Tag.query.filter(Tag.name == sys.argv[3]).one()

        tagbuild(sys.argv[4], bkoji, btag)


    elif sys.argv[1] == "untagbuild":

        assert len(sys.argv) == 5

        bkoji = Koji.query.filter(Koji.name == sys.argv[2]).one()

        btag = Tag.query.filter(Tag.name == sys.argv[3]).one()

        untagbuild(sys.argv[4], bkoji, btag)

    elif sys.argv[1] == "update":

        assert len(sys.argv) == 4

        update(sys.argv[2], sys.argv[3])

    elif sys.argv[1] == "getbuild":

        assert len(sys.argv) == 4

        getbuild(int(sys.argv[3]), sys.argv[2])

    elif sys.argv[1] == "delbuild":

        assert len(sys.argv) == 4

        delbuild(int(sys.argv[3]), sys.argv[2])




