#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# GitHub repository listing for an org
#
# Copyright (C) 2016 Bitergia
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
import argparse
import json
import logging
import sys

import requests

from datetime import datetime
from time import sleep

from dateutil import parser
from grimoire_elk.utils import config_logging

GITHUB_API_URL = "https://api.github.com"
GITHUB_URL = "https://github.com"
NREPOS = 0  # all


def get_params():
    """Parse command line arguments"""

    parser = argparse.ArgumentParser()

    parser.add_argument('-g', '--debug', dest='debug', action='store_true')
    parser.add_argument('-m', '--mordred', dest='mordred', action='store_true',
                        help="Generate mordred projects file")
    parser.add_argument('-t', '--token', dest='token', help="GitHub token")
    parser.add_argument('-o', '--owner', dest='owner', help='GitHub owner (user or org) to be analyzed')
    parser.add_argument('-n', '--nrepos', dest='nrepos', type=int, default=NREPOS,
                        help='Number of GitHub repositories from the Organization to be analyzed (default:10)')

    params = parser.parse_args()

    if not params.owner:
        print("owner param is needed")
        sys.exit(1)

    return params

def get_payload():
    # 100 max in repos
    payload = {'per_page': 100,
               'fork': False,
               'sort': 'updated', # does not work in repos listing
               'direction': 'desc'}
    return payload

def get_headers(token):
    headers = {}
    if token:
        headers = {'Authorization': 'token ' + token}
    return headers

def get_owner_repos_url(owner, token):
    """ The owner could be a org or a user.
        It waits if need to have rate limit.
        Also it fixes a djando issue changing - with _
    """
    url_org = GITHUB_API_URL+"/orgs/"+owner+"/repos"
    url_user = GITHUB_API_URL+"/users/"+owner+"/repos"

    url_owner = url_org  # Use org by default

    try:
        r = requests.get(url_org,
                         params=get_payload(),
                         headers=get_headers(token))
        r.raise_for_status()

    except requests.exceptions.HTTPError as e:
        if r.status_code == 403:
            rate_limit_reset_ts = datetime.fromtimestamp(int(r.headers['X-RateLimit-Reset']))
            seconds_to_reset = (rate_limit_reset_ts - datetime.utcnow()).seconds+1
            logging.info("GitHub rate limit exhausted. Waiting %i secs for rate limit reset." % (seconds_to_reset))
            sleep(seconds_to_reset)
        else:
            # owner is not an org, try with a user
            url_owner = url_user
    return url_owner

def get_repositories(owner, token, nrepos):
    """ owner could be an org or and user """
    all_repos = []

    owner_url = get_owner_repos_url(owner, token)

    url = owner_url

    while True:
        logging.debug("Getting repos from: %s", url)
        try:
            r = requests.get(url,
                            params=get_payload(),
                            headers=get_headers(token))

            r.raise_for_status()
            all_repos += r.json()

            logging.debug("Rate limit: %s", r.headers['X-RateLimit-Remaining'])


            if 'next' not in r.links:
                break

            url = r.links['next']['url']  # Loving requests :)
        except requests.exceptions.ConnectionError:
            logging.error("Can not connect to GitHub")
            break

    # Remove forks
    nrepos_recent = [repo for repo in all_repos if not repo['fork']]
    # Sort by updated_at and limit to nrepos
    nrepos_sorted = sorted(nrepos_recent,
                           key=lambda repo: parser.parse(repo['updated_at']),
                           reverse=True)
    if nrepos > 0:
        nrepos_sorted = nrepos_sorted[0:nrepos]
    # First the small repositories to feedback the user quickly
    nrepos_sorted = sorted(nrepos_sorted, key=lambda repo: repo['size'])
    for repo in nrepos_sorted:
        logging.debug("%s %i %s", repo['updated_at'], repo['size'], repo['name'])
    return nrepos_sorted

def get_mordred_projects(owner, repos):
    # Sample format
    # {
    #     "grimoire": {
    #         "git": [
    #             "https://github.com/grimoirelab/perceval",
    #             "https://github.com/grimoirelab/arthur",
    #             "https://github.com/grimoirelab/grimoireelk"
    #         ],
    #         "github": [
    #             "https://github.com/grimoirelab/perceval"
    #         ]
    #     }
    # }

    owner_url = GITHUB_URL+"/"+owner+"/"
    projects = {
        owner:
            {
                "git": [],
                "github": []
            }
    }
    for repo in repos:
        projects[owner]["git"].append(owner_url + repo['name'])
        projects[owner]["github"].append(owner_url + repo['name'])
    return projects

if __name__ == '__main__':
    args = get_params()
    config_logging(args.debug)
    repos = get_repositories(args.owner, args.token, args.nrepos)
    if not args.mordred:
        for repo in repos:
            print(repo['name'])
    else:
        prj_file = args.owner + "-projects.json"
        logging.info("Generating mordred projects file in %s", prj_file)
        projects = get_mordred_projects(args.owner, repos)
        with open (prj_file, "w") as f:
            json.dump(projects, f, indent=4)
