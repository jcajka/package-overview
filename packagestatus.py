#!/usr/bin/python

# packagestatus: cli tool to get package/tag overview across kojis
# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>

import koji
import re
import logging
import time
from multiprocessing import Pool, freeze_support
from rpm import labelCompare

PROCESSES_COUNT = 4

FEDORA_KOJI_BASE_URL = 'koji.fedoraproject.org/kojihub'
FEDORA_KOJIS = [{'name':'primary', 'prefix':''},
                {'name':'s390', 'prefix':'s390.'},
                {'name':'ppc', 'prefix':'ppc.'},
                {'name':'arm', 'prefix':'arm.'},
               ]

DT = 1000
R = 1
V = 1000
_NONE = 3000

def get_distance(builds, ox=FEDORA_KOJIS[0], oy=0):

    kojis = FEDORA_KOJIS

    logging.debug("Calculating build distance matrix")

    dm = dict()

    for hub in builds:
        dm[hub] = [0, 0]
    if not builds[ox['name']][oy]:
        logging.debug("Missing build in origin. Looking in secondary ...")
        for hub in kojis:
            if builds[hub['name']][oy]:
                ox = hub
                logging.debug("Found new origin build=%s",
                              (builds[ox['name']][oy]))
                break
    logging.debug("Prepared zero matrix dm=%s", dm)
    if not builds[ox['name']][oy]:
        logging.debug('Missing origin(Tagged builds)...')
        #probably not a problem
        return dm
    for hub in builds:
        for y in range(2):
            # no need to compare to origin
            if hub == ox['name'] and y == oy:
                logging.debug("Origin skipping ...")
                continue
            # no build ever, not a problem
            if not builds[hub][0] and not builds[hub][1]:
                logging.debug("No builds skipping hub ...")
                break
            #no build to compare to...
            if not builds[hub][y]:
                logging.debug("Missing build...")
                continue


            comp = labelCompare(getevr(builds[ox['name']][oy]),
                                getevr(builds[hub][y]))
            # same NVR distance 0
            if comp == 0:
                logging.debug("Same NVR skipping ...")
                continue
            # we need to get actual distance
            logging.debug("Comparing NVR")
            srel1 = builds[ox['name']][oy]['release'].split('.')
            srel2 = builds[hub][y]['release'].split('.')

            logging.debug("Split release, srel1=%s, srel2=%s",
                          srel1,
                          srel2)

            m1 = re.match('\D+(?P<rel>\d+)\D*', srel1[len(srel1)-1])
            m2 = re.match('\D+(?P<rel>\d+)\D*', srel2[len(srel2)-1])

            if m1 and m2:
                logging.debug("Found dist release number")
                pdtag1 = int(m1.group('rel'))
                pdtag2 = int(m2.group('rel'))
            else:
                logging.warn("Could not determine dist release number")
                pdtag1 = 0
                pdtag2 = 0

            try:
                prel1 = int(srel1[len(srel1)-2])
                prel2 = int(srel2[len(srel2)-2])
            except ValueError:
                logging.warn("Could not determine release number")
                prel1 = 0
                prel2 = 0

            vdiff = versiondiff(builds[ox['name']][oy]['version'],
                                builds[hub][y]['version'])
            dt = pdtag1-pdtag2
            if dt > 3:
                vdiff -= dt*DT
            else:
                vdiff += dt*DT
            vdiff += (prel1-prel2)*R
            logging.debug("Package distance d=%s", (vdiff))
            dm[hub][y] = vdiff
            if not builds[hub][0] and y == 1:
                logging.debug("Missing tagged build. Using last build distance")
                dm[hub][0] = dm[hub][y]
    return dm

# positive if v1 is greater negative if v2 is greater
def versiondiff(v1, v2):
    logging.debug("Getting version distance between v1=%s v2=%s", v1, v2)
    sv1 = v1.split('.')
    sv2 = v2.split('.')

    mul = 1

    ret = 0

    i = 0
    while True:
        if len(sv1) == 0 or len(sv2) == 0 or i > 3:
            if len(sv2) > len(sv1):
                ret -= V//mul
            if len(sv1) > len(sv2):
                ret += V//mul
            break
        st = re.sub(r"\D", "", sv1.pop(0))
        nd = re.sub(r"\D", "", sv2.pop(0))
        st = 0 if not st else int(st)
        nd = 0 if not nd else int(nd)
        ret += (st-nd)*(V//mul)
        mul *= 2
        i += 1
    logging.debug("Distance vd=%s", (ret))
    return ret

def do_onhub(url, method, args, kwargs):
    logging.debug("Doing on hub=%s, method=%s, with args=%s kwargs=%s",
                  url,
                  method,
                  args,
                  kwargs)
    session = koji.ClientSession(url)
    ret = getattr(session, method)(*args, **kwargs)
    return ret

def valueinmaplist(value, key, mapList, pop=False):
    ret = -1
    for i in range(len(mapList)):
        if value == mapList[i][key]:
            ret = i
            if pop:
                mapList.pop(i)
            break
    return ret

def getevr(build):
    if build is None:
        raise Exception("build is None")
    ret = ('0' if not build['epoch'] else str(build['epoch']),
           build['version'],
           build['release'])
    return ret

def validpackagename(name):
    m = re.match('[\w.+-]*', name)
    if len(m.group(0)) != len(name):
        return False
    return True

def validtagname(tag):
    return validpackagename(tag)

def get_tagsoverview(baseURL=FEDORA_KOJI_BASE_URL, kojis=FEDORA_KOJIS):

    logging.info("Getting tags overview.")

    pool = Pool(processes=PROCESSES_COUNT)

    try:

        tries = 0
        results = dict()
        tagSet = dict()

        while tries < 5:
            try:
                logging.debug("Retrieving tags lists.")
                for hub in kojis:
                    url = 'http://'+hub['prefix']+baseURL
                    args = url, 'listTags', (), {}
                    results[hub['name']] = pool.apply_async(do_onhub, args)

                for hub in kojis:
                    tagSet[hub['name']] = results[hub['name']].get(timeout=10)
                break
            except:
                tries += 1
                if tries >= 5:
                    raise
                time.sleep(2)
                logging.warn("Retrying...")
                results = dict()
                tagSet = dict()

        processed = []

        logging.debug("Processing lists.")

        for hub in kojis:
            for tag in tagSet[hub['name']]:
                line = dict()
                line[hub['name']] = tag
                line['name'] = tag['name']
                for tkoji in kojis:
                    if tkoji['name'] is hub['name']:
                        continue
                    v = valueinmaplist(tag['name'],
                                       'name',
                                       tagSet[tkoji['name']])
                    if v > -1:
                        line[tkoji['name']] = tagSet[tkoji['name']][v]
                        del tagSet[tkoji['name']][v]
                    else:
                        line[tkoji['name']] = None
                processed.append(line)


        logging.info("Done")
    finally:
        pool.close()
        pool.join()

    return processed



def get_packagesoverview(tag='f21',
                         srt=True,
                         baseURL=FEDORA_KOJI_BASE_URL,
                         kojis=FEDORA_KOJIS,
                         verbose=True):

    pool = Pool(processes=PROCESSES_COUNT)

    try:

        logging.info("Getting packages overview for tag=%s ", (tag))

        results = dict()
        packageLists = dict()
        tries = 0

        while tries < 5:

            try:

                logging.debug("Getting tagged packages.")

                for hub in kojis:
                    url = 'http://'+hub['prefix']+baseURL
                    args = url, 'listTagged', (tag, ), {'latest':True}
                    results[hub['name']] = pool.apply_async(do_onhub, args)

                for hub in kojis:
                    packageLists[hub['name']] = results[hub['name']].get(timeout=3000)

                break

            except:

                tries += 1
                if tries >= 5:
                    raise
                time.sleep(2)
                logging.warn("Retrying...")
                results = dict()
                packageLists = dict()

        logging.debug("Done")
        for l in packageLists:
            logging.debug("Package count c=%s", (len(packageLists[l])))

        ret = []

        # get last successful

        logging.debug("Processing builds")

        for hub in kojis:
            for package in packageLists[hub['name']]:
                line = dict()
                bs = dict()

                line['name'] = package['package_name']
                bs[hub['name']] = [package]
                for pkoji in kojis:

                    if hub['name'] is pkoji['name']:
                        continue

                    vl = -1
                    vl = valueinmaplist(line['name'],
                                        'package_name',
                                        packageLists[pkoji['name']])
                    if vl > -1:
                        bs[pkoji['name']] = [packageLists[pkoji['name']].pop(vl)]
                    else:
                        bs[pkoji['name']] = [None]

                line['builds'] = bs
                ret.append(line)

        logging.debug("Done")

        if verbose is True:
            logging.debug("Getting last successful builds")
            for package in ret:
                logging.debug("Getting last attempted for %s", (package['name']))
                package['builds'] = get_packageoverview(package['name'],
                                                        tag,
                                                        baseURL=baseURL,
                                                        kojis=kojis,
                                                        bs=package['builds'])
        if srt is True:
            logging.debug("Sorting")
            ret = sorted(ret, key=lambda pkg: pkg['name'])

        logging.info("Done")
    finally:
        pool.close()
        pool.join()

    return ret


def get_tagoverview(tag, baseURL=FEDORA_KOJI_BASE_URL, kojis=FEDORA_KOJIS):

    pool = Pool(processes=PROCESSES_COUNT)

    tries = 0

    while tries < 5:

        try:
            results = dict()

            for hub in kojis:
                url = 'http://'+hub['prefix']+baseURL
                args = url, 'getTag', (tag, ), {}
                results[hub['name']] = pool.apply_async(do_onhub, args)

            tids = dict()

            tids['name'] = tag

            for hub in kojis:
                tids[hub['name']] = results[hub['name']].get(timeout=10)
                if tids[hub['name']]:
                    assert tids[hub['name']]['name'] == tag

            break

        except:
            tries += 1
            if tries >= 5:
                raise
            time.sleep(2)
            logging.warn("Retrying...")
            results = dict()

        finally:
            pool.close()
            pool.join()

    return tids


def get_packageoverview(package, tag,
                        baseURL=FEDORA_KOJI_BASE_URL,
                        kojis=FEDORA_KOJIS, bs=None):

    logging.info("Getting builds for package %s in tag %s", package, tag)
    
    pool = Pool(processes=PROCESSES_COUNT)

    try:

        m = re.match('\D+(?P<rel>\d+)\D*', tag)
        rel = -1
        if m:
            rel = int(m.group('rel'))

        logging.debug("Determined rel=%s", rel)
        
        if bs is None:
            logging.debug("bs==None, retriving tagged builds")
            bs = dict()
            results = dict()
            pkgIDs = dict()
            tries = 0

            while tries < 5:

                try:

                    for hub in kojis:
                        url = 'http://'+hub['prefix']+baseURL
                        args = url, 'getPackageID', (package, ), {}
                        results[hub['name']] = pool.apply_async(do_onhub, args)

                    for hub in kojis:
                        packageid = results[hub['name']].get(timeout=30)
                        if packageid is None:
                            pool.close()
                            pool.join()
                            logging.warn("No builds found on koji.")
                            return None
                        pkgIDs[hub['name']] = packageid

                    break

                except:
                    tries += 1
                    if tries >= 5:
                        raise
                    time.sleep(2)
                    logging.warn("Failed to get pkgIDs, retrying...")
                    results = dict()
                    pkgIDs = dict()


            logging.debug("PkgsID=%s", (pkgIDs))

            results = dict()
            tries = 0

            while tries < 5:

                try:

                    for hub in kojis:
                        url = 'http://'+hub['prefix']+baseURL
                        args = url, 'getTagID', (tag,), {}
                        ktag = pool.apply_async(do_onhub, args).get(timeout=30)
                        #tag exists on koji
                        if ktag:
                            args = url, 'listTagged', (tag, ), {'latest':True,
                                                                'package':package}
                            results[hub['name']] = pool.apply_async(do_onhub, args)
                        else:
                            results[hub['name']] = None
    
                    for hub in kojis:
                        if results[hub['name']]:
                            bs[hub['name']] = results[hub['name']].get(timeout=30)
                        else:
                            bs[hub['name']] = [None]

                    break

                except:

                    tries += 1
                    if tries >= 5:
                        raise
                    logging.warn("Failed to list tagged, retrying...")
                    results = dict()
                    bs = dict()

            logging.debug("Done")
    
        logging.debug("Retriving latest builds")

        results = dict()
        retries = 0
        while retries < 5:

            try:
                for hub in kojis:
                    if bs[hub['name']] and bs[hub['name']][0]:
                        date = bs[hub['name']][0]['creation_time']
                    else:
                        date = None
            
                    packageid = None
    
                    if bs[hub['name']] and bs[hub['name']][0]:
                        packageid = bs[hub['name']][0]['package_id']
                    #missing tagged build retriving package id from koji
                    else:
                        tries = 0
                        while tries < 5:
                            try:
                                packageid = pool.apply_async(do_onhub,
                                                             ('http://' + hub['prefix'] + baseURL,
                                                              'getPackageID', 
                                                              (package, ),
                                                              {})).get(timeout=30)
                                break
                            except:
                                tries += 1
                                if tries >= 5:
                                    raise
                                logging.warn("Failed to retrieve pkgID, retrying...")
                                time.sleep(2)

                    assert packageid

                    kwar = {"packageID": packageid, "createdAfter":date}
                    url = 'http://' + hub['prefix'] + baseURL
                    args = url, "listBuilds", (), kwar,
                    results[hub['name']] = pool.apply_async(do_onhub, args)
    
                for hub in kojis:
                    if bs[hub['name']]:
                        bs[hub['name']] += results[hub['name']].get(timeout=30)
                    else:
                        bs[hub['name']] = [None]
                        bs[hub['name']] += results[hub['name']].get(timeout=30)

                break

            except:
                retries += 1
                if retries >= 5:
                    raise
                logging.warn("Failed to list builds, retrying...")
                time.sleep(2)
    
        logging.debug("Done")

        line = dict()

        logging.debug("Searching for latest.")

        for hub in kojis:
            latest = None
            for build in bs[hub['name']]:
                if build is None:
                    continue
                if latest is None:
                    if rel > 0:
                        m = re.match(".*fc(?P<rel>\d+).*", build["release"])
                        if m and int(m.group("rel")) <= rel:
                            latest = build
                        else:
                            try:
                                bid = build['build_id']
                            except KeyError:
                                logging.warn("Using id instead of build_id")
                                bid = build['id']
                            logging.debug("Build %s(%s) is too new. Skipping...",
                                          bid,
                                          hub['name'])
                        
                    continue

                comp = labelCompare(getevr(latest), getevr(build))

                #latest have same or newer NVR 
                if comp == 0 or comp > 0:
                    continue

                else: 
                    if rel > 0:
                        m = re.match(".*fc(?P<rel>\d+).*", build["release"])

                        if m is None:
                            logging.warn("Couldn't determine realease from %s",
                                         build['release'])
                            continue #not a Fedora release

                        drel = int(m.group("rel"))

                        logging.debug("Comparing drel=%s to rel=%s", drel, rel)
                        # too new release
                        if drel > rel:
                            logging.debug("Skipping based on comparison. Too new...")
                            continue

                    latest = build

            #finished looking for latest build
            item = [bs[hub['name']][0], latest if latest else bs[hub['name']][0]]
            line[hub['name']] = item

    finally:
        pool.close()
        pool.join()

    logging.info("Done")
    return line

if __name__ == "__main__":

    import argparse

    freeze_support()
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--verbose',
                           action='store_true',
                           help='enables additional output, overrides --quiet')
    argparser.add_argument('--quiet',
                           action='store_true',
                           help='suppresses non error related output')
    argparser.add_argument('tag', nargs='?', help="Build tag")
    argparser.add_argument('package', nargs='?', help="Package name")
    arg = argparser.parse_args()

    if arg.verbose:
        loglevel = logging.DEBUG
    elif arg.quiet:
        loglevel = logging.ERROR
    else:
        loglevel = logging.INFO

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        level=loglevel)

    if arg.tag is None and arg.package is None:

        header = 'Name' + 34 * ' '

        overview = get_tagsoverview()

        for khub in FEDORA_KOJIS:
            header += ' '+khub['name']+' '
        print header

        for oline in overview:
            out = oline['name']
            out += ' ' * (40-len(oline['name'])) 
            for khub in FEDORA_KOJIS:
                if oline[khub['name']]:
                    out += '   +  '#+str(oline[khub['name']]['id'])
                else:
                    out += '   -  '
            print out

    elif arg.package is None: 

        pkgs = get_packagesoverview(tag=arg.tag)
        for pkg in pkgs:
            oline = ""
            oline += pkg['name']
            oline += '\n'
            for khub in FEDORA_KOJIS:
                print pkg['builds']
                oline += '\t'
                if pkg['builds'][khub['name']][0]:
                    oline += str(pkg['builds'][khub['name']][0]['version'])
                    oline += '-'
                    oline += str(pkg['builds'][khub['name']][0]['release'])
                    oline += '\n'
                else:
                    oline += 'None\n'
                oline += '\t'
                if len(pkg['builds'][khub['name']]) > 1 and\
                   pkg['builds'][khub['name']][1]:
                    oline += str(pkg['builds'][khub['name']][1]['version'])
                    oline += '-'
                    oline += str(pkg['builds'][khub['name']][1]['release'])
                    oline += '\n'
                else:
                    oline += 'None\n'
            print oline

        print "Package count: %d" % len(pkgs)

    else:
        p = str(arg.package)
        t = str(arg.tag)
        if not validpackagename(p):
            print "Invalid package name."
            exit(-1)
        if not validtagname(t):
            print "Invalid tag name."
            exit(-1)
        kbuilds = get_packageoverview(p, t)
        if kbuilds is None:
            print "Package with name %s doesn't exist." % p
            exit(-1)
        for khub in FEDORA_KOJIS:
            print khub['name']+':'
            for obuild in kbuilds[khub['name']]:
                if obuild is None:
                    print  '\tNone'
                else:
                    print '\t', obuild['nvr']
                    print '\t', koji.BUILD_STATES[obuild['state']]

        distancem = get_distance(kbuilds)
        print distancem
    logging.info("Finished")
