#!/usr/bin/python

# Copyright (C) 2015 Red Hat, Inc.
# SPDX-License-Identifier:      GPL-2.0
#
# Authors:
#       Jakub Cajka <jcajka@redhat.com>
import unittest
import sys
sys.path.append("../")
from mockclasses.mockpool import mockpool
from unittest import TestCase
from mock import patch
from packagestatus import get_tagsoverview, get_tagoverview, get_packageoverview

# Tag pools

class TestTagPool1(mockpool):

    responses = {"http://koji": [[{"name": "f1"}, {"name": "f2"}],]}

class TestTagPool2(mockpool):

    responses = {"http://koji0": [[{"name": "f1"}, {"name": "f2"}],],
                 "http://koji1": [[{"name": "f3"}, {"name": "f2"}],],
                 "http://koji2": [[{"name": "f4"}, {"name": "f2"}],]
                 }

class TestTagPool3(mockpool):

    responses = {"http://koji": [{"name": "f1"}, ]}

class TestTagPool4(mockpool):

    responses = {"http://koji0": [{"name": "f1"}, ],
                 "http://koji1": [None,],
                 "http://koji2": [{"name": "f1"}, ]
                 }

class TestTagPool5(mockpool):

    responses = {"http://koji0": [None, ],
                 "http://koji1": [None, ],
                 "http://koji2": [None, ]
                 }

class TestTagPool6(mockpool):
         
    responses = {"http://koji": [[]], }

# Package pools

class TestPackagePool1(mockpool):

    responses = {"http://koji": [ 1, 1,
                                 [{"build_id": 1, "package_name": "p",
                                   "nvr": "p-1.3.2-4.fc1",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "4.fc1", "package_id": 1,
                                   "id": 1, "name": "p"},
                                  ],
                                 [{"build_id": 1, "package_name": "p",
                                   "nvr": "p-1.3.2-4.fc1",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "4.fc1", "package_id": 1,
                                   "id": 1, "name": "p"},
                                  ],
                                 ],}
class TestPackagePool2(mockpool):

    responses = {"http://koji": [ 1, 1,
                                 [{"build_id": 1, "package_name": "p",
                                   "nvr": "p-1.3.2-4.fc1",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "4.fc1", "package_id": 1,
                                   "id": 1, "name": "p"},
                                  ],
                                 [{"build_id": 2, "package_name": "p",
                                   "nvr": "p-1.3.2-5.fc2",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "5.fc2", "package_id": 1,
                                   "id": 2, "name": "p"},
                                  {"build_id": 1, "package_name": "p",
                                   "nvr": "p-1.3.2-4.fc1",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "4.fc1", "package_id": 1,
                                   "id": 1, "name": "p"}
                                  ],
                                 ],}

class TestPackagePool3(mockpool):

    responses = {"http://koji": [ 1, 1,
                                 [{"build_id": 1, "package_name": "p",
                                   "nvr": "p-1.3.2-4.fc1",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "4.fc1", "package_id": 1,
                                   "id": 1, "name": "p"},
                                  ],
                                 [{"build_id": 2, "package_name": "p",
                                   "nvr": "p-1.3.2-5.fc1",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "5.fc1", "package_id": 1,
                                   "id": 2, "name": "p"},
                                  {"build_id": 1, "package_name": "p",
                                   "nvr": "p-1.3.2-4.fc1",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "4.fc1", "package_id": 1,
                                   "id": 1, "name": "p"}
                                  ],
                                 ],}

class TestPackagePool4(mockpool):

    responses = {"http://koji": [ 1, 1, None, 1,
                                 [{"build_id": 3, "package_name": "p",
                                   "nvr": "p-1.3.2-4.fc2",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "4.fc2", "package_id": 1,
                                   "id": 3, "name": "p"},
                                  {"build_id": 2, "package_name": "p",
                                   "nvr": "p-1.3.2-5.fc0",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "5.fc0", "package_id": 1,
                                   "id": 2, "name": "p"},
                                  {"build_id": 1, "package_name": "p",
                                   "nvr": "p-1.3.2-4.fc0",
                                   "creation_time": "2014-12-03 19:06:02.434976",
                                   "epoch": None, "version": "1.3.2",
                                   "release": "4.fc0", "package_id": 1,
                                   "id": 1, "name": "p"}
                                  ],
                                 ],}

class TestPackagePool5(mockpool):

    responses = {"http://koji": [ None , ], }

class TestPackagePool6(mockpool):

    responses = {"http://koji": [ 1, None , 1, []], }



class basictagtests(TestCase):

    @patch("packagestatus.Pool", new=TestTagPool1)
    def test_tagsoverview_onekoji(self):
        expectedtag = [{'koji': {'name': 'f1'}, 'name': 'f1'}, {'koji': {'name': 'f2'}, 'name': 'f2'}] 
        tag = get_tagsoverview(baseURL="", kojis=[ {"name" : "koji", "prefix" : "koji"}])
        self.assertEqual(tag, expectedtag)

    @patch("packagestatus.Pool", new=TestTagPool2)
    def test_tagsoverview_threekojis(self):
        expectedtag = [{'koji2': None, 'name': 'f1', 'koji0': {'name': 'f1'}, 'koji1': None},
                       {'koji2': {'name': 'f2'}, 'name': 'f2', 'koji0': {'name': 'f2'}, 'koji1': {'name': 'f2'}},
                       {'koji2': None, 'name': 'f3', 'koji0': None, 'koji1': {'name': 'f3'}},
                       {'koji2': {'name': 'f4'}, 'name': 'f4', 'koji0': None, 'koji1': None}]

        tag = get_tagsoverview(baseURL="", kojis=[ {"name" : "koji0", "prefix" : "koji0"},
                                                   {"name" : "koji1", "prefix" : "koji1"},
                                                   {"name" : "koji2", "prefix" : "koji2"},
                                                 ])
        self.assertEqual(tag, expectedtag)

    @patch("packagestatus.Pool", new=TestTagPool3)
    def test_tagoverview_onekoji(self):
        expectedtag = {'name': 'f1', 'koji': {'name': 'f1'}} 
        tag = get_tagoverview("f1", baseURL="" , kojis=[ {"name" : "koji", "prefix" : "koji"}])
        self.assertEqual(tag, expectedtag)

    @patch("packagestatus.Pool", new=TestTagPool4)
    def test_tagoverview_threekojis(self):
        expectedtag = {'koji2': {'name': 'f1'}, 'name': 'f1', 'koji0': {'name': 'f1'}, 'koji1': None} 
        tag = get_tagoverview("f1", baseURL="", kojis=[ {"name" : "koji0", "prefix" : "koji0"},
                                                        {"name" : "koji1", "prefix" : "koji1"},
                                                        {"name" : "koji2", "prefix" : "koji2"},
                                                      ])
        self.assertEqual(tag, expectedtag)

    @patch("packagestatus.Pool", new=TestTagPool5)
    def test_tagoverview_threekojis_none(self):
        expectedtag = {'koji2': None, 'name': 'f1', 'koji0': None, 'koji1': None}
        tag = get_tagoverview("f1", baseURL="", kojis=[ {"name" : "koji0", "prefix" : "koji0"},
                                                        {"name" : "koji1", "prefix" : "koji1"},
                                                        {"name" : "koji2", "prefix" : "koji2"},
                                                      ])
        self.assertEqual(tag, expectedtag)

    @patch("packagestatus.Pool", new=TestTagPool6)
    def test_tagoverview_onekoji_notags(self):

        expectedtag = []

        tag = get_tagsoverview(baseURL="", kojis=[ {"name" : "koji", "prefix" : "koji"}])

        self.assertEqual(tag, expectedtag)

    @patch("packagestatus.Pool", new=TestPackagePool1)
    def test_packageoverview_onekoji(self):
        expectedbuilds =  {'koji': [{'build_id': 1, 'epoch': None, 'version': '1.3.2', 'nvr': 'p-1.3.2-4.fc1', 'package_name': 'p', 'release': '4.fc1', 'name': 'p', 'creation_time': '2014-12-03 19:06:02.434976', 'package_id': 1, 'id': 1}, {'build_id': 1, 'epoch': None, 'version': '1.3.2', 'nvr': 'p-1.3.2-4.fc1', 'package_name': 'p', 'release': '4.fc1', 'name': 'p', 'creation_time': '2014-12-03 19:06:02.434976', 'package_id': 1, 'id': 1}]}
        builds = get_packageoverview("p", "f1", baseURL="", kojis=[ {"name" : "koji", "prefix" : "koji"}])
        self.assertEqual(builds, expectedbuilds)

    @patch("packagestatus.Pool", new=TestPackagePool2)
    def test_packageoverview_onekoji_nextreleasebuild(self):

        expectedbuilds = {'koji': [{'build_id': 1, 'epoch': None, 'version': '1.3.2', 'nvr': 'p-1.3.2-4.fc1', 'package_name': 'p', 'release': '4.fc1', 'name': 'p', 'creation_time': '2014-12-03 19:06:02.434976', 'package_id': 1, 'id': 1}, {'build_id': 1, 'epoch': None, 'version': '1.3.2', 'nvr': 'p-1.3.2-4.fc1', 'package_name': 'p', 'release': '4.fc1', 'name': 'p', 'creation_time': '2014-12-03 19:06:02.434976', 'package_id': 1, 'id': 1}]}
      
        builds = get_packageoverview("p", "f1", baseURL="", kojis=[ {"name" : "koji", "prefix" : "koji"}])
        self.assertEqual(builds, expectedbuilds) 

    @patch("packagestatus.Pool", new=TestPackagePool3)
    def test_packageoverview_onekoji_newerbuild(self):

        expectedbuilds = {'koji': [{'build_id': 1, 'epoch': None, 'version': '1.3.2', 'nvr': 'p-1.3.2-4.fc1', 'package_name': 'p', 'release': '4.fc1', 'name': 'p', 'creation_time': '2014-12-03 19:06:02.434976', 'package_id': 1, 'id': 1}, {'build_id': 2, 'epoch': None, 'version': '1.3.2', 'nvr': 'p-1.3.2-5.fc1', 'package_name': 'p', 'release': '5.fc1', 'name': 'p', 'creation_time': '2014-12-03 19:06:02.434976', 'package_id': 1, 'id': 2}]}

        builds = get_packageoverview("p", "f1", baseURL="", kojis=[ {"name" : "koji", "prefix" : "koji"}])
        self.assertEqual(builds, expectedbuilds)

    @patch("packagestatus.Pool", new=TestPackagePool4)
    def test_packageoverview_onekoji_notagged_older(self):

        expectedbuilds = {'koji': [None, {'build_id': 2, 'epoch': None, 'version': '1.3.2', 'nvr': 'p-1.3.2-5.fc0', 'package_name': 'p', 'release': '5.fc0', 'name': 'p', 'creation_time': '2014-12-03 19:06:02.434976', 'package_id': 1, 'id': 2}]}

        builds = get_packageoverview("p", "f1", baseURL="", kojis=[ {"name" : "koji", "prefix" : "koji"}])
        self.assertEqual(builds, expectedbuilds)

    @patch("packagestatus.Pool", new=TestPackagePool5)
    def test_packageoverview_onekoji_nobuilds(self):
       #TODO suppress Warning/Error messages
        builds = get_packageoverview("p", "f1", baseURL="", kojis=[ {"name" : "koji", "prefix" : "koji"}])
        self.assertEqual( builds, None )

    @patch("packagestatus.Pool", new=TestPackagePool6)
    def test_packageoverview_onekoji_notag_nobuilds(self):
          
        expectedbuilds = {'koji': [None, None]}

        builds = get_packageoverview("p", "f1", baseURL="", kojis=[ {"name" : "koji", "prefix" : "koji"}])
        self.assertEqual( builds, expectedbuilds)

if __name__ == '__main__':
    unittest.main()
