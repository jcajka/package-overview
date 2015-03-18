#!/usr/bin/python

# statusweb: package overview web app
# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>
from packagestatus import get_packageoverview, get_tagsoverview, get_tagoverview
from packagestatus import validtagname, get_distance, validpackagename
from packagestatus import FEDORA_KOJIS, FEDORA_KOJI_BASE_URL

from flask import Flask, render_template, request, redirect, abort, url_for
from flask.ext.sqlalchemy import SQLAlchemy

from rpm import labelCompare
from collections import OrderedDict

import json
import re
import datetime
import urllib2
import logging
import string

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://user:password@localhost/database"
db = SQLAlchemy(app)
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG)

def initdb():
    logging.info("Preparing DB")
    logging.info("Dropping DB")
    db.drop_all()
    logging.info("Creating DB tables")
    db.create_all()
    logging.info("Done")

    #create kojis
    logging.info("Creating koji entries")
    for hub in FEDORA_KOJIS:
        koji = Koji(hub['name'], hub['prefix'], FEDORA_KOJI_BASE_URL)
        db.session.add(koji)
    db.session.commit()
    logging.info("Done")

    #create tags and find active (Active/Under Development) ones
    logging.info("Creating tag entries")
    _get_tagsoverview()
    db.session.commit()
    logging.info("Done")

    logging.info("Marking active tags")
    r = urllib2.urlopen('https://admin.fedoraproject.org/pkgdb/api/collections/?pattern=f*&clt_status=Active')
    active = r.read()
    r = urllib2.urlopen('https://admin.fedoraproject.org/pkgdb/api/collections/?pattern=f*&clt_status=Under%20Development')
    dev = r.read()

    tags = Tag.query.all()

    assert tags

    totag = []

    if active:
        active = json.loads(active)
        for i in active["collections"]:
            totag.append(i['koji_name'])

    if dev:
        dev = json.loads(dev)
        if dev["collections"]:
            for i in dev["collections"]:
                totag.append(i['koji_name'])
        # no development for f*, this means rawhide
        # so we need to determine next fedora release
        # according to last release number
        else:
            last = None
            for t in totag:
                num = None
                try:
                    num = int(t.lstrip(string.ascii_letters))
                except ValueError, e:
                    logging.warn("Unable determine to active tag %s release", t)
                    logging.exception(e)
                    continue
                assert num
                if not last:
                    last = num
                    continue
                if last < num:
                    last = num
            if last:
                totag.append("f"+str(last+1))
            else:
                logging.warn("No development tag found.")

    # mark fedora-updates as active
    for t in totag[:]:
        totag.append(t+"-updates")

    for tag in tags:
        if tag.name in totag:
            tag.active = True
            db.session.merge(tag)

    db.session.commit()

    logging.info("Done")

def _createtag(tag):

    tags = get_tagoverview(tag)

    kojis = Koji.query.all()

    empty = True
    if tags:
        for k in tags:
            if k == 'name':
                continue
            if tags[k]:
                empty = False
                break
    # tag is not pressent on koji
    if not tags or empty:
        logging.warn("Tag %s doesn't exist", tag)
        return None
    assert tags['name'] == tag
    dtag = Tag(tags['name'], json.dumps(tags))

    for hub in kojis:
        if tags[hub.name]:
            dtag.kojis.append(hub)

    db.session.add(dtag)

    return dtag

def llNotEmpty(ll):
    if not ll:
        return False
    for i in ll:
        if not i:
            return False
    return True

def _get_tagsoverview():

    logging.debug("Retriving tags overview")
    kojis = Koji.query.all()
    assert kojis
    ret_tags = []
    ret_tags = Tag.query.all()
    if llNotEmpty(ret_tags) and ret_tags:
        logging.debug("Using DB")
        dec = []
        for tag in ret_tags:
            dec.append(json.loads(json.loads(tag.tag))) # TODO single json.loads is not enought ??!!
        ret_tags = dec
    else:
        logging.debug("Using Koji")
        ret_tags = get_tagsoverview()
        for tag in ret_tags:
            dtag = Tag(tag['name'], json.dumps(tag))
            for hub in kojis:
                if tag[hub.name]:
                    dtag.kojis.append(hub)
            db.session.add(dtag)
    logging.debug("Done")
    return ret_tags

def get_tagrel(tag):
    mtch = re.match(".*f(?P<rel>\d*).*", tag)
    if mtch:
        drel = int(mtch.group("rel"))
    else:
        logging.warn("Couldn't determine rel from %s", tag)
        drel = 9999
    return drel

def _get_packageoverview(package, tag, nokoji=False):

    logging.debug("Getting overview for %s in %s", package, tag)
    kojis = Koji.query.all()
    dtag = Tag.query.filter(Tag.name == tag).first()
    dpackage = Package.query.filter(Package.name == package).first()

    #missing tag
    if not dtag:
        logging.warn("Missing tag %s. Creating", tag)
        try:
            dtag = _createtag(tag)
            db.session.commit()
        except BaseException, e:
            db.session.rollback()
            raise e
        if not dtag:
            return None

    drel = get_tagrel(dtag.name)

    ktbuilds = None
    lbuild = None

    if dtag and dpackage:
        ktbuilds = Build.query.filter(Build.tags.any(id=dtag.id),
                                      Build.package_id == dpackage.id
                                     ).order_by(Build.koji_id).all()
        if ktbuilds or (not ktbuilds and nokoji):
            lbuild = Build.query.filter(Build.package_id == dpackage.id,
                                        Build.distrel <= drel
                                       ).order_by(Build.koji_id).all()

    rbuilds = dict()

    if ktbuilds or (nokoji and lbuild):
        logging.debug("Builds should be in DB.")
        for hub in kojis:
            if ktbuilds:
                ktbuild = filter(lambda x: x.koji_id == hub.id, ktbuilds)
                ktbuild.sort(key=lambda z: z.fdate, reverse=True)
                if ktbuild:
                    ktbuild = ktbuild[0]
                else:
                    ktbuild = None
            else:
                ktbuild = None
            lbuilds = filter(lambda x: x.koji_id == hub.id, lbuild)
            latest = None

            if ktbuild:
                latest = ktbuild
                #print "Tagged"+ktbuild.build
                #print hub.name
            elif lbuilds:
                latest = lbuilds[0]

            if len(lbuilds) > 1:
                for build in lbuilds:
                    #print "latest"+build.build
                    if build.id == latest.id:
                        continue
                   # print latest
                    cmpr = labelCompare(latest.getevr(),
                                        build.getevr())

                    if cmpr >= 0:
                        continue
                    else:
                        latest = build

            rbuilds[hub.name] = [ktbuild if ktbuild else None,
                                 latest if latest else None]
    else:
        if nokoji:
            return None
        logging.debug("Using Koji")

        rbuilds = get_packageoverview(package, tag)

        if not rbuilds:
            logging.debug("Package %s doesn't exist.", package)
            return rbuilds

        ex = False

        # Do we have any build?

        for r in rbuilds:
            if r:
                for b in r:
                    if b:
                        # we do
                        ex = True
                        break

        if not ex:
            return None

        # missing package in DB
        if not dpackage:
            logging.debug("Creating package %s", package)
            dpackage = Package(package)
            db.session.add(dpackage)

        rel = drel
        logging.debug("Processing builds...")
        for hub in kojis:
            for b in range(2):
                if not rbuilds[hub.name][b]:
                    continue

                #is it in db?
                dbuild = Build.query.filter(Build.bid == rbuilds[hub.name][b]['build_id'],
                                            Build.koji_id == hub.id).first()
                if dbuild:
                    logging.debug("Already in DB.")
                    pb = dbuild

                else:
                    logging.debug("Creating")
                    mtch = re.match(".*fc(?P<rel>\d*).*",
                                    rbuilds[hub.name][b]['release'])
                    if mtch:
                        rel = int(mtch.group('rel'))
                    else:
                        logging.debug("Couldn't determine rel from: %s",
                                      rbuilds[hub.name][b]['release'])
                        rel = None

                    pb = Build(json.dumps(rbuilds[hub.name][b]),
                               rbuilds[hub.name][b]['build_id'],
                               dpackage.id,
                               rel,
                               datetime.datetime.strptime(rbuilds[hub.name][b]["creation_time"],
                                                          "%Y-%m-%d %H:%M:%S.%f"))
                    pb.state = rbuilds[hub.name][b]['state']
                    pb.version = rbuilds[hub.name][b]['version']
                    pb.release = rbuilds[hub.name][b]['release']
                    pb.epoch = rbuilds[hub.name][b]['epoch'] if rbuilds[hub.name][b]['epoch'] else '0'
                # tagging latest build is not needed, as it won't be latest if tagged...
                if b is not 1:

                    # we belive koji that it returned tagged build...
                    # as builds in multiple tags seems to miss tag property
                    assert dtag
                    if not dtag in pb.tags:
                        pb.tags.append(dtag)
                        logging.debug("Appended tag %s to build %s",
                                      dtag.name, pb.bid)
                    else:
                        if not dbuild:
                            logging.warn("Build %s, already tagged in to %s",
                                         str(pb),
                                         dtag.name)
                        else:
                            logging.debug("Same build, already tagged.")
                # we have build already in Db just checking integrity
                if dbuild:
                    assert pb.koji_id == hub.id

                pb.koji_id = hub.id

                db.session.merge(pb)
    logging.debug("Done")
    return rbuilds


@app.route('/')
def home():
    activetags = Tag.query.filter(Tag.active == True).order_by(Tag.name.desc()).all()
    return render_template('master.html', activetags=activetags)

@app.route('/<package>/<tagname>')
def packageTag(tagname, package):

    builds = dict()
    if validpackagename(package) and validtagname(tagname):
        try:
            dbuilds = _get_packageoverview(package, tagname)
            tag = Tag.query.filter(Tag.name == tagname).first()
            kojis = Koji.query.all()
            activetags = Tag.query.filter(Tag.active == True).order_by(Tag.name.desc()).all()
            db.session.commit()
        except BaseException:
            db.session.rollback()
            logging.exception("Unhandled exception during package overview processing...")
            abort(500)
        if dbuilds:
            dm = get_distance(dbuilds)
            builds = (dbuilds, dm)
        if not tag:
            #TODO better error handling?
            logging.error("Missing tag %s", tagname)
            abort(404)
    return render_template('packagetag.html',
                           package=package,
                           tag=tag,
                           kojis=kojis,
                           builds=builds,
                           activetags=activetags)

@app.route('/tags')
def tagsOverview():
    try:
        tags = _get_tagsoverview()
        db.session.commit()
        kojis = Koji.query.all()
        activetags = Tag.query.filter(Tag.active == True).order_by(Tag.name.desc()).all()
    except BaseException:
        db.session.rollback()
        logging.exception("Unhandled exception during tags overview processing...")
        abort(500)
    return render_template('tags.html',
                           tags=tags,
                           kojis=kojis,
                           activetags=activetags)

@app.route('/tags/<tag>')
def tagOverview(tag):
    packages = None
    activetags = Tag.query.filter(Tag.active == True).order_by(Tag.name.desc()).all()
    return render_template('packages.html',
                           tag=tag,
                           packages=packages,
                           activetags=activetags)

@app.route('/search', methods=['POST', 'GET'])
def search():
    if request.method == 'POST':
        if request.form['package'] and request.form['tag']:
            logging.debug("Search for %s %s", request.form['package'], request.form['tag'])
            return redirect(url_for('packageTag',
                                    tagname=request.form['tag'],
                                    package=request.form['package']), code=303)
        else:
            abort(400)
    else:
        abort(405)

@app.route('/ftbfs/<tag>')
def problems(tag):
    #print "Args"+json.dumps(request.args)
    kojis = Koji.query.all()
    dtag = Tag.query.filter(Tag.name == tag).one()
    if not dtag:
        abort(404)
    rel = get_tagrel(dtag.name)
    # get packages with failed build
    fpackagesq = Package.query.join(Build).filter(Build.state == 3,
                                                  Build.distrel == rel,
                                                  Build.tags == None)
    # filter based on koji
    ids = []
    filterbykoji = False

    for koji in kojis:
        if koji.name in request.args and request.args[koji.name] == 'on':
            ids.append(koji.id)
            filterbykoji = True

    if ids:
        fpackagesq = fpackagesq.filter(Build.koji_id.in_(ids))

    fpackages = fpackagesq.all()

    issues = dict()
    for package in fpackages:
        # get really failed builds
        bs = _get_packageoverview(package.name, tag, nokoji=True)
        failed = False
        #print bs
        fids = []
        for koji in kojis:
            if bs[koji.name][1] and bs[koji.name][1]['state'] == 3:
                if not filterbykoji:
                    failed = True
                    break
                else:
                    fids.append(koji.id)
                    continue
        if fids and set(ids).issubset(set(fids)):
            failed = True

        if failed:
            issues[package.name] = (bs, get_distance(bs))
        else:
            continue

    if 'sortby' in request.args and 'order' in request.args:
        order = request.args['order'] == 'desc'
        if request.args['sortby'] == 'name':
            #print "SORTING"
            issues = OrderedDict(sorted(issues.items(),
                                        key=lambda t: t[0].lower(),
                                        reverse=order))
    else:
        issues = OrderedDict(sorted(issues.items(),
                                    key=lambda t: t[0].lower(),
                                    reverse=False))
    activetags = Tag.query.filter(Tag.active == True).order_by(Tag.name.desc()).all()
    #print "RENDERING"
    return render_template('ftbfs.html',
                           tag=dtag,
                           issues=issues,
                           kojis=kojis,
                           activetags=activetags)

@app.route('/<package>/')
def packageStatus(package):
    kojis = Koji.query.all()
    tags = Tag.query.filter(Tag.active == True).all()
    ret = dict()
    for tag in tags:
        if tag.name == "f22-updates":
            continue
        try:
            ret[tag.name] = _get_packageoverview(package, tag.name)
            ret[tag.name] = (ret[tag.name], get_distance(ret[tag.name]))
            # commit progress
            db.session.commit()
        except BaseException:
            db.session.rollback()
            logging.exception("Unhandled exception during tags overview processing...")
            abort(500)
    package = Package.query.filter(Package.name == package).one()
    return render_template('packageoverview.html',
                           tags=tags,
                           activetags=tags,
                           package=package,
                           overview=ret,
                           kojis=kojis)

# for tags in build
T_TAGS = db.Table('tags',
                  db.Column('tag_id',
                            db.Integer,
                            db.ForeignKey('tag.id')),
                  db.Column('build_id',
                            db.Integer,
                            db.ForeignKey('build.id')))
# for kojia in tag
T_KOJIS = db.Table('kojis',
                   db.Column('tag_id',
                             db.Integer,
                             db.ForeignKey('tag.id')),
                   db.Column('koji_id',
                             db.Integer,
                             db.ForeignKey('koji.id')))

class Build(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    build = db.Column(db.Text)
    epoch = db.Column(db.String)
    version = db.Column(db.String)
    release = db.Column(db.String)
    bid = db.Column(db.Integer)
    package_id = db.Column(db.Integer, db.ForeignKey('package.id'))
    distrel = db.Column(db.Integer)
    fdate = db.Column(db.DateTime)
    tags = db.relationship('Tag',
                           secondary=T_TAGS,
                           backref=db.backref('builds', lazy='dynamic'))
    koji_id = db.Column(db.Integer, db.ForeignKey('koji.id'))
    state = db.Column(db.Integer)

    def __init__(self, build, bid, pid, drel, fdate):
        self.build = build
        self.package_id = pid
        self.distrel = drel
        self.fdate = fdate
        self.bid = bid

    def __getitem__(self, key):
        if key == "version":
            return self.version
        elif key == "release":
            return self.release if self.release else ""
        elif key == "epoch":
            return self.epoch if self.epoch else None
        elif key == "state":
            return self.state
        elif key == "build_id":
            return self.bid
        elif key == "nvr":
            return Package.query.filter(Package.id == self.package_id).one().name + "-" + self.version + "-" + self.release
        else:
            raise KeyError()

    def getevr(self):
        return (self.epoch, self.version, self.release)

class Package(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    builds = db.relationship('Build',
                             backref='package',
                             lazy='dynamic')

    def __init__(self, name):
        self.name = name

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    tag = db.Column(db.Text)
    active = db.Column(db.Boolean)
    kojis = db.relationship("Koji",
                            secondary=T_KOJIS,
                            backref=db.backref('tags', lazy='dynamic'))

    def __init__(self, name, tag, active=False):
        self.name = name
        self.active = active
        self.tag = json.dumps(tag)


class Koji(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    prefix = db.Column(db.String)
    url = db.Column(db.String)
    builds = db.relationship('Build',
                             backref='koji',
                             lazy='dynamic')

    def __init__(self, name, prefix, url):
        self.name = name
        self.prefix = prefix
        self.url = url

    def getURL(self, protocol="http://"):
        return protocol + self.prefix + self.url

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000, debug=True)
