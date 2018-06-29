#!/usr/bin/python

# =========================== adjust path =====================================

import sys
import os

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'smartmeshsdk', 'libs'))

# =========================== imports =========================================

# from default Python
import time
import json
import subprocess
import threading
import logging.config

# third-party packages
import bottle
import influxdb

# project-specific
import solserver_version
from   dustCli               import DustCli
from   sensorobjectlibrary   import Sol as sol, \
                                    SolExceptions,\
                                    SolUtils

#============================ logging =========================================

logging.config.fileConfig('logging.conf')
log = logging.getLogger('solserver')
log.setLevel(logging.DEBUG)

#============================ defines =========================================

CONFIGFILE         = 'solserver.config'
STATSFILE          = 'solserver.stats'

ALLSTATS           = [
    #== admin
    'ADM_NUM_CRASHES',
    #== connection to server
    'JSON_NUM_REQ',
    'JSON_NUM_UNAUTHORIZED',
    #== DB
    'DB_NUM_WRITES_OK',
    'DB_NUM_WRITES_FAIL',
    'NUM_SET_ACTION_REQ',
    'NUM_OBJECTS_DB_FAIL',
    'NUM_OBJECTS_DB_OK',
    'NUM_JSON_REQ',
]

#============================ helpers =========================================

#============================ classes =========================================

#======== JSON API to receive notifications from SolManager


class JsonApiThread(threading.Thread):

    def __init__(self):

        # local variables
        self.sites                = []
        self.influxClient         = influxdb.client.InfluxDBClient(
            host        = SolUtils.AppConfig().get('influxdb_host'),
            port        = SolUtils.AppConfig().get('influxdb_port'),
            database    = SolUtils.AppConfig().get('influxdb_database'),
        )
        self.actions    = []

        # initialize web server
        self.web        = bottle.Bottle()
        # interaction with SolManager
        self.web.route(
            path        = '/api/v1/o.json',
            method      = 'PUT',
            callback    = self._webhandle_o_PUT,
        )
        self.web.route(
            path        = '/api/v1/getactions/',
            method      = 'GET',
            callback    = self._webhandle_getactions_GET,
        )
        # interaction with administrator
        self.web.route(
            path        = '/api/v1/echo.json',
            method      = 'POST',
            callback    = self._webhandle_echo_POST,
        )
        self.web.route(
            path        = '/api/v1/status.json',
            method      = 'GET',
            callback    = self._webhandle_status_GET,
        )
        self.web.route(
            path        = '/api/v1/setaction/',
            method      = 'POST',
            callback    = self._webhandle_setactions_POST,
        )

        # start the thread
        threading.Thread.__init__(self)
        self.name       = 'JsonApiThread'
        self.daemon     = True
        self.start()

    def run(self):
        try:
            self.web.run(
                host   = '0.0.0.0',
                port   = SolUtils.AppConfig().get('solserver_tcpport'),
                quiet  = True,
                debug  = False,
            )

        except bottle.BottleException:
            raise

        except Exception as err:
            SolUtils.logCrash(err, SolUtils.AppStats(), threadName=self.name)

        log.info("JsonApiThread started")

    #======================== public ==========================================

    def close(self):
        # bottle thread is daemon, it will close when main thread closes
        pass

    def set_action(self, action):
        action_exists = False
        for item in self.actions:
            if cmp(action, item) == 0:
                action_exists = True
        if not action_exists:
            self.actions.append(action)

    def get_actions(self, site):
        actions = []
        for item in self.actions:
            if item["site"] == site:
                actions.append(item)
        self.actions = []  # removing previous actions
        return actions

    #======================== private =========================================

    #=== webhandlers

    # decorator
    def _authorized_webhandler(func):
        def hidden_decorator(self):
            try:
                # update stats
                SolUtils.AppStats().increment('JSON_NUM_REQ')

                # authorize the client
                siteName = self._authorizeClient(
                    token = bottle.request.headers.get('X-REALMS-Token'),
                )

                # abort if not authorized
                if not siteName:
                    return bottle.HTTPResponse(
                        body   = json.dumps({'error': 'Unauthorized'}),
                        status = 401,
                        headers= {'Content-Type': 'application/json'},
                    )

                # abort if not valid JSON payload
                if bottle.request.json is not None:
                    try:
                        json.dumps(bottle.request.json)
                    except ValueError:
                        return bottle.HTTPResponse(
                            body   = json.dumps(
                                {'error': 'Malformed JSON body'}
                            ),
                            status = 400,
                            headers= {'Content-Type': 'application/json'},
                        )

                # retrieve the return value
                returnVal = func(self, siteName=siteName)

                # send back answer
                return bottle.HTTPResponse(
                    status  = 200,
                    headers = {'Content-Type': 'application/json'},
                    body    = json.dumps(returnVal),
                )

            except SolExceptions.UnauthorizedError:
                return bottle.HTTPResponse(
                    status  = 401,
                    headers = {'Content-Type': 'application/json'},
                    body    = json.dumps({'error': 'Unauthorized'}),
                )
            except Exception as err:

                crashMsg = SolUtils.logCrash(err, SolUtils.AppStats())

                return bottle.HTTPResponse(
                    status  = 500,
                    headers = {'Content-Type': 'application/json'},
                    body    = json.dumps(crashMsg),
                )
        return hidden_decorator

    # interaction with SolManager

    @_authorized_webhandler
    def _webhandle_o_PUT(self, siteName=None):

        # abort if not  JSON payload
        if bottle.request.json is None:
            return bottle.HTTPResponse(
                body=json.dumps(
                    {'error': 'JSON body is required'}
                ),
                status=400,
                headers={'Content-Type': 'application/json'},
            )

        # http->bin
        try:
            sol_binl = sol.http_to_bin(bottle.request.json)
        except:
            return bottle.HTTPResponse(
                body   = json.dumps(
                            {'error': 'Malformed JSON body contents'}
                        ),
                status = 400,
                headers= {'Content-Type': 'application/json'},
            )

        # bin->json->influxdb format, then write to put database
        sol_influxdbl = []
        for sol_bin in sol_binl:

            # convert bin->json
            sol_json          = sol.bin_to_json(sol_bin)

            # convert json->influxdb
            tags = self._get_tags(siteName, sol_json["mac"])
            sol_influxdbl    += [sol.json_to_influxdb(sol_json, tags)]

        # write to database
        try:
            self.influxClient.write_points(sol_influxdbl)
        except:
            SolUtils.AppStats().increment('NUM_OBJECTS_DB_FAIL')
            raise
        else:
            SolUtils.AppStats().increment('NUM_OBJECTS_DB_OK')

    @_authorized_webhandler
    def _webhandle_getactions_GET(self, siteName=None):
        """
        Triggered when the solmanager requests the solserver for actions

        Ex:
           1. solmanager asks solserver for actions
           2. solserver tells solmanager to update its SOL library
        """

        return self.get_actions(siteName)

    # interaction with administrator

    @_authorized_webhandler
    def _webhandle_echo_POST(self, siteName=None):

        return bottle.request.body.read()

    @_authorized_webhandler
    def _webhandle_status_GET(self, siteName=None):
        return {
                'version solserver': solserver_version.VERSION,
                'version Sol': list(sol.version()),
                'uptime computer': self._exec_cmd('uptime'),
                'utc': int(time.time()),
                'date': time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime()),
                #'last reboot': self._exec_cmd('last reboot'),  # TODO not working anymore
                'stats': SolUtils.AppStats().get()
        }

    @_authorized_webhandler
    def _webhandle_setactions_POST(self, siteName=None):
        """
        Add an action to passively give order to the solmanager.
        When the solmanager can't be reached by the solserver, the solmanager
        periodically ask the server for actions.
        """

        # format action
        action_json = {
            "action":   bottle.request.json["action"],
            "site":     bottle.request.json["site"],
        }

        # add action to list if action is available
        available_actions = ["update"]
        if bottle.request.json["action"] in available_actions:
            self.set_action(action_json)

        return "Action OK"

    #=== misc

    def _get_tags(self, site_name, mac):
        """
        :param str mac : a dash-separated mac address
        :return: the tags associated to the given mac address
        :rtype: dict
        Notes: tags are read from 'site.py' file
        """
        return_tags = {"mac": mac}  # default tag is only mac
        for site in self.sites:
            if site["name"] == site_name:
                for key, tags in site["motes"].iteritems():
                    if mac == key:
                        return_tags.update(tags)
                        return_tags["site"] = site["name"]
        return return_tags

    def _authorizeClient(self, token=None):

        assert token

        siteName             = None
        searchAfterReload    = False
        while True:
            for site in self.sites:
                if site['token'] == token:
                    siteName = site["name"]
                    break
            if (not siteName) and (searchAfterReload is False):
                with open('solserver.sites', 'r') as f:
                    self.sites = json.load(f)["sites"]
                searchAfterReload = True
            else:
                break

        if not siteName:
            SolUtils.AppStats().increment('JSON_NUM_UNAUTHORIZED')

        return siteName

    @staticmethod
    def _exec_cmd(cmd):
        try:
            returnVal = subprocess.check_output(cmd, shell=False)
        except subprocess.CalledProcessError:
            returnVal = "ERROR"
        return returnVal

#======== main application thread


class SolServer(object):

    def __init__(self):

        # init Singletons -- must be first init
        SolUtils.AppConfig(config_file=CONFIGFILE)
        SolUtils.AppStats(stats_file=STATSFILE, stats_list=ALLSTATS)

        # API thread
        self.jsonApiThread  = JsonApiThread()

        # CLI interface
        self.cli            = DustCli.DustCli("SolServer", self._clihandle_quit)
        self.cli.registerCommand(
            name                       = 'stats',
            alias                      = 's',
            description                = 'print the stats',
            params                     = [],
            callback                   = self._clihandle_stats,
        )

    @staticmethod
    def _clihandle_quit():
        time.sleep(.3)
        print "bye bye."
        # all threads as daemonic, will close automatically

    @staticmethod
    def _clihandle_stats(params):
        stats = SolUtils.AppStats().get()
        output = []
        for k in sorted(stats.keys()):
            output += ['{0:<30}: {1}'.format(k, stats[k])]
        output = '\n'.join(output)
        print output

# =========================== main ============================================


def main():
    SolServer()

if __name__ == '__main__':
    main()
