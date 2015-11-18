#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Perceval Backend base class 
#
# Copyright (C) 2015 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#   Alvaro del Castillo San Felix <acs@bitergia.com>
#
# Bugzilla backend for Perseval

''' Backend define the API to be supported in Perceval data sources backends '''

import json
import logging
import os
from os.path import expanduser, join
import requests
import traceback

from perceval.cache import CacheItems


class Backend(object):

    # Public Perceval backend API 
    def fetch(self):
        ''' Returns an iterator for the data gathered '''
        raise NotImplementedError


    def get_id(self):
        '''Unique identifier for a backend instance '''
        raise NotImplementedError


    def set_elastic(self, elastic):
        ''' Elastic used to store last data source state '''
        self.elastic = elastic


    # Internal class implementation

    @classmethod
    def add_params(cls, cmdline_parser):
        ''' Shared params in all backends '''

        parser = cmdline_parser

        parser.add_argument("--no_incremental",  action='store_true',
                            help="don't use last state for data source")
        parser.add_argument("--cache",  action='store_true',
                            help="Use cache")
        parser.add_argument("--debug",  action='store_true',
                            help="Increase logging to debug")
        parser.add_argument("-e", "--elastic_host",  default="127.0.0.1",
                            help="Host with elastic search" +
                            "(default: 127.0.0.1)")
        parser.add_argument("--elastic_port",  default="9200",
                            help="elastic search port " +
                            "(default: 9200)")


    def __init__(self, use_cache = False, incremental = True):

        self.cache = CacheItems(self._get_storage_dir(), 
                                self._get_field_unique_id())
        self.use_cache = use_cache
        self.incremental = incremental

        # Create storage dir if it not exists
        dump_dir = self._get_storage_dir()
        if not os.path.isdir(dump_dir):
            os.makedirs(dump_dir)

        if self.use_cache:
            # Don't use history data. Will be generated from cache.
            self.incremental = False

        if self.incremental:
            self._restore_state()  # Load last state

        else:
            if not self.use_cache:
                self.cache.clean()  # Cache will be refreshed


    def _get_field_unique_id(self):
        ''' Field with the unique id for the JSON items '''
        raise NotImplementedError


    def _items_state_to_es(self, json_items):
        ''' Append items JSON to ES (data source state) '''

        if len(json_items) == 0:
            return

        field_id = self._get_field_unique_id()

        elasticsearch_type = "state"
        url = self.elastic.index_url+'/'+elasticsearch_type+'/_bulk'

        logging.debug("Adding %i items (%s state) to %s" % (len(json_items),
                                                            self._get_name(),
                                                            url))

        bulk_json = ""
        for item in json_items:
            data_json = json.dumps(item)
            bulk_json += '{"index" : {"_id" : "%s" } }\n' % (item[field_id])
            bulk_json += data_json +"\n"  # Bulk document

        requests.put(url, data=bulk_json)


    def _restore_state(self):
        ''' Restore data source state from last execution '''
        logging.info("State restore not implemented. Incremental disabled.")
        self.incremental = False


    def _get_name(self):
        ''' Human name for the backend class '''
        raise NotImplementedError


    def _get_storage_dir(self):

        home = expanduser("~")
        '''Get directory in which to store backend data'''
        _dir = join(home, ".perceval", self._get_name(), self.get_id())

        return _dir
