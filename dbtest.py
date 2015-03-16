#!/usr/bin/python

# dbtest: test basic db related functions, similar to coherencetest
# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>
from statusweb import _get_tagsoverview, _get_packageoverview, db, initdb
from statusweb import Koji

import koji
import random
import logging

def equalbs(st, nd):

    kojis = Koji.query.all()

    diff = {}

    if st and nd:
        if not len(st) == len(nd):
            logging.debug("build comparison failed: diffrent length.")
            return False
        for hub in kojis:
            if st[hub.name] and nd[hub.name]:
                for i in range(2):
                    if st[hub.name][i] and nd[hub.name][i]:
                        uncommon = set(st[hub.name][i].keys()) ^ set(nd[hub.name][i].keys())
                        if uncommon:
                            logging.warn("Missmatching build key sets: %s", uncommon)
                        # keys ignored in comparison as koji is some times bit inconsistent...,
                        # or we are handling it incorrectly...
                        ignored = set(['tag_name', 'tag_id', 'id', 'creation_ts', 'completion_ts'])
                        if not uncommon or not uncommon - ignored:
                            for item in st[hub.name][i]:
                                if item in ignored:
                                    logging.warning("Skipping %s as key is in ignored %s",
                                                    item,
                                                    ignored)
                                    continue
                                if st[hub.name][i][item] != nd[hub.name][i][item]:
                                # may compare str with unicode, but it shouldn't be a problem in fedora, as package name
                                # contain only ascii characters(package naming guidelines)
                                    logging.debug("build comparison failed: missmatching properties %s: %s != %s.",
                                                  item,
                                                  st[hub.name][i][item],
                                                  nd[hub.name][i][item])
                                    if not hub.name in diff:
                                        diff[hub.name] = [dict(st[hub.name][i]), dict(nd[hub.name][i])]
                                        if i == 0:
                                            diff[hub.name][0]['tagged'] = True
                        else:
                            logging.debug("build comparison failed: diffrence in build keys sets:\n%s.",
                                          uncommon)
                            diff[hub.name] = [st[hub.name][i], nd[hub.name][i]]
                            continue
                    elif st[hub.name][i] != nd[hub.name][i]:
                        logging.debug("build comparison failed: missmatching builds(probably one is None)")
                        diff[hub.name] = [st[hub.name][i], nd[hub.name][i]]
                        continue
            elif st[hub.name] != nd[hub.name]:
                diff[hub.name] = [st[hub.name], nd[hub.name]]
                continue
        return diff
    raise ValueError("Function argument(s) shouldn't be empty/None.")

# Will drop database
def testPrep():

    initdb()


def tagTest():

    try:
        tagsKoji = _get_tagsoverview()
        db.session.commit()
        tagsDb = _get_tagsoverview()
        db.session.commit()
    except BaseException, e:
        db.session.rollback()
        raise e

    kj = Koji.query.all()

    assert kj

    if len(tagsKoji) != len(tagsDb):
        logging.error("Number of tags is diffrent.")
        return False

    missing = []
    diff = []

    for t in tagsKoji:
        found = False
        equal = False

        d = None

        for d in tagsDb:
            if d['name'] == t['name']:
                found = True
                for k in kj:
                    if d[k.prefix] and not [k.prefix]:
                        break
                    if not d[k.prefix] and t[k.prefix]:
                        break
                    if d[k.prefix] and t[k.prefix] and not d[k.prefix]['id'] == t[k.prefix]['id']:
                        break
                equal = True
                break

        assert d

        if not found:
            missing.append(t)
        if not equal:
            diff.append((t, d))

    if missing:
        logging.info("Missing tags in DB:")
        for m in missing:
            logging.info("%s", m)

    if diff:
        logging.info("Not maching tags:")
        for t in diff:
            logging.info("%s", t)

    if not missing and not diff:
        return True
    else:
        return False

def testPackages(tag, number=None, lst=None):
    
    if not number and not lst:
        return

    kj = Koji.query.all()
    
    assert kj

    ch = None

    if number and lst:
    
        session = koji.ClientSession("http://koji.fedoraproject.org/kojihub")
        packages = session.listPackages()
    
        logging.info("Selecting packages randomly...")
        ch = random.sample(packages, number)

    else:
        if not lst:
            raise ValueError("All provided arguments are Null") 
        logging.info("Using provided list...")
        ch = lst
    
    logging.info("Selected packages:")
    for p in ch:
        logging.info("%s", p['package_name'])

    missmatch = []
    
    for p in ch:
        try:
            pkoji = _get_packageoverview(p['package_name'], tag)
            db.session.commit()
            pdb = _get_packageoverview(p['package_name'], tag)
            db.session.commit()
        except BaseException, e:
            db.session.rollback()
            raise e
        equal = equalbs(pkoji, pdb)
        
        if not equal:
            missmatch.append((p, pkoji, pdb))
                
        logging.info("--------------------")
        logging.info("%s\nEqual: %s", p, equal)
        logging.info("--------------------")


    logging.info("--------------------")
    logging.info("Summary:")
    for i in missmatch:
        logging.info("%s", i)
    logging.info("--------------------")


if __name__ == '__main__':
    testPackages('f21', number=10)
