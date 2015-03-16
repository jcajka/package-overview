#!/usr/bin/python

# fedmsgwatch: listens to fedmsg for koji envent and updates DB
# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>
import fedmsg

from statusweb import Build, Tag, Koji, Package, db
from statusweb import _get_packageoverview, _createtag
from dbutils import getbuild
import json
import koji as kj
import datetime
import re
import urllib2
import logging


KOJITOPIC = "org.fedoraproject.prod.buildsys."
PKGDBTOPIC = "org.fedoraproject.prod.pkgdb."


def processevent(topic, msg):
    if topic.endswith("build.state.change"):
        logging.debug('Processing build state change')

        koji = Koji.query.filter(Koji.name == msg['msg']['instance']).one()
        assert koji

        package = Package.query.filter(Package.name == msg['msg']['name']).first()

        if not package:
            logging.warn("Package %s is missing", msg['msg']['name'])
            package = Package(msg['msg']['name'])
            db.session.add(package)
            db.session.commit()
            logging.debug("Created package %s", msg['msg']['name'])
            logging.debug("Getting active tag builds.")
            atags = Tag.query.filter(Tag.active == True).all()
            for tag in atags:
                _get_packageoverview(msg['msg']['name'], tag.name)
                logging.debug("For tag %s", tag.name)
            logging.debug("Done")


        build = Build.query.filter(Build.bid == msg['msg']['build_id'],
                                   Build.koji_id == koji.id).first()

        if not package and build:
            logging.error("Missing package %s, but do have build...",
                          package.name)
            return
        logging.debug("Retriving build %s from %s",
                      msg['msg']['build_id'],
                      koji.name)
        kojisession = kj.ClientSession(koji.getURL())
        kojibuild = kojisession.getBuild(msg['msg']['build_id'])
        logging.debug("Done.")

        assert kojibuild

        #fix koji build format to be consistent with list_tagged,...
        if not 'build_id' in kojibuild:
            assert kojibuild['id']
            kojibuild['build_id'] = kojibuild['id']
        if not 'id' in kojibuild:
            assert kojibuild['build_id']
            kojibuild['id'] = kojibuild['build_id']
        if 'completion_ts' in kojibuild:
            del kojibuild['completion_ts']
        if 'creation_ts' in kojibuild:
            del kojibuild['creation_ts']
        logging.info('Fixing build %s from %s JSON format',
                     kojibuild['build_id'],
                     koji.name)

        # sanity check, shouldn't happen, but it does...
        # as koji might try to "lie" to us about build state...
        if kojibuild['state'] != msg['msg']['new']:
            # koji returned inconsistent build state...
            logging.warning('Fixing build %s from %s, build state(%s->%s)',
                            kojibuild['build_id'],
                            koji.name,
                            kojibuild['state'],
                            msg['msg']['new'])
            kojibuild['state'] = msg['msg']['new']

        #just update
        if build:
            logging.debug("Updating build.")
            build.build = json.dumps(kojibuild)
            build.state = kojibuild['state']
        #build is missing
        else:
            logging.debug("Creating build.")
            mtch = re.match(".*fc(?P<rel>\d*).*", kojibuild['release'])
            if not mtch:
                logging.warn("Not a fc build.")
                return
            rel = int(mtch.group('rel'))

            build = Build(json.dumps(kojibuild),
                          kojibuild['build_id'],
                          package.id,
                          rel,
                          datetime.datetime.strptime(kojibuild["creation_time"],
                                                     "%Y-%m-%d %H:%M:%S.%f"))
            build.state = kojibuild['state']
            build.version = kojibuild['version']
            build.release = kojibuild['release']
            build.epoch = kojibuild['epoch'] if kojibuild['epoch'] else '0'
            build.koji_id = koji.id

        db.session.merge(build)
        logging.debug("Done")

    elif topic.endswith('untag') or \
         topic.endswith('tag'):
        logging.debug("Processing tag change")

        koji = Koji.query.filter(Koji.name == msg['msg']['instance']).one()

        build = Build.query.filter(Build.bid == msg['msg']['build_id'],
                                   Build.koji_id == koji.id).first()

        tag = Tag.query.filter(Tag.kojis.any(id=koji.id),
                               Tag.name == msg['msg']['tag']).first()

        if topic.endswith('tag') and not tag:
            logging.warn("Missing tag %s, creating...", msg['msg']['tag'])
            tag = _createtag(msg['msg']['tag'])

        if not build:
            #we may miss the build...
            if not tag.active:
                logging.warn("Missing build %s", msg['msg']['build_id'])
                return
            #we need to get a missed build...
            build = getbuild(msg['msg']['build_id'], koji.name)

        assert tag

        logging.debug("Updating build %s", build.bid)
        if topic.endswith('untag'):
            build.tags = filter(lambda x: x.id != tag.id, build.tags)
            logging.debug("Untagged from %s", tag.name)
        else:

            if not tag in build.tags:
                build.tags.append(tag)
                logging.debug("Tagged in to %s", tag.name)
            else:
                logging.warn("Build %s, already tagged in to %s",
                             str(build),
                             tag.name)

        db.session.merge(build)
        logging.debug("Done")

    elif topic.endswith("collection.new") or \
         topic.endswith("collection.update"):
        logging.debug("Processing tag %s update.",
                      msg['msg']['collection']['branchname'])
        tagname = msg['msg']['collection']['branchname']
        tag = Tag.query.filter(Tag.name == tagname).first()
        if not tag:
            logging.warn("Creating new tag.")
            tag = _createtag(tagname)
        #is it active tag? or does it changed?
        qurl = "https://admin.fedoraproject.org/pkgdb/api/collections/?pattern=%s" % tagname
        buf = urllib2.urlopen(qurl)
        res = buf.read()
        res = json.loads(res)
        if len(res['collections']) > 1:
            logging.warning('More than 1 active tag for %s using first...,\n%s',
                            tagname,
                            res)
        if res['collections'][0]['status'] == 'Active' or \
           res['collections'][0]['status'] == "Under Development":
            logging.debug("Setting %s as active", tagname)
            tag.active = True
        else:
            logging.debug("Setting %s as not active", tagname)
            tag.active = False

        db.session.merge(tag)
        logging.debug("Done")

if __name__ == "__main__":
    logging.info("Starting up...")
    assert db
    logging.info("Done.")
    for name, endpoint, ftopic, fmsg in fedmsg.tail_messages():
        if ftopic.startswith(KOJITOPIC) or ftopic.startswith(PKGDBTOPIC):
            logging.debug("Processing topic %s", ftopic)
            try:
                processevent(ftopic, fmsg)
                db.session.commit()
            except Exception:
                db.session.rollback()
                logging.exception("Runtime exception")
