#!/usr/bin/python

# =========================== adjust path =====================================

import sys
import os

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'sol'))

# =========================== imports =========================================

# from default Python
import pickle
import time
import json
import subprocess
import threading
import traceback
import datetime
from   optparse                 import OptionParser
from   ConfigParser             import SafeConfigParser
import logging
import logging.config

# third-party packages
import bottle
import influxdb

# project-specific
import OpenCli
from solobjectlib import Sol, SolVersion
import solserver_version
import sites

#============================ logging =========================================

logging.config.fileConfig('logging.conf')
log = logging.getLogger('solserver')
log.setLevel(logging.DEBUG)

#============================ defines =========================================

DEFAULT_TCPPORT              = 8081
DEFAULT_SOLSERVERHOST        = '0.0.0.0' # listen on all interfaces

DEFAULT_CONFIGFILE           = 'solserver.config'
DEFAULT_CRASHLOG             = 'solserver.crashlog'
DEFAULT_BACKUPFILE           = 'solserver.backup'

# config file

DEFAULT_SOLMANAGERTOKEN      = 'DEFAULT_SOLMANAGERTOKEN'
DEFAULT_SOLSERVERCERT        = 'solserver.cert'
DEFAULT_SOLSERVERPRIVKEY     = 'solserver.ppk'

# stats

STAT_NUM_JSON_REQ            = 'NUM_JSON_REQ'
STAT_NUM_JSON_UNAUTHORIZED   = 'NUM_JSON_UNAUTHORIZED'
STAT_NUM_CRASHES             = 'NUM_CRASHES'
STAT_NUM_OBJECTS_DB_OK       = 'STAT_NUM_OBJECTS_DB_OK'
STAT_NUM_OBJECTS_DB_FAIL     = 'STAT_NUM_OBJECTS_DB_FAIL'
STAT_NUM_SET_ACTION_REQ      = 'NUM_SET_ACTION_REQ'

#============================ helpers =========================================

def logCrash(threadName,err):
    output  = []
    output += ["============================================================="]
    output += [time.strftime("%m/%d/%Y %H:%M:%S UTC",time.gmtime())]
    output += [""]
    output += ["CRASH in Thread {0}!".format(threadName)]
    output += [""]
    output += ["=== exception type ==="]
    output += [str(type(err))]
    output += [""]
    output += ["=== traceback ==="]
    output += [traceback.format_exc()]
    output  = '\n'.join(output)
    # update stats
    AppData().incrStats(STAT_NUM_CRASHES)
    print output
    log.critical(output)

#============================ classes =========================================

class AppData(object):
    _instance = None
    _init     = False
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AppData,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    def __init__(self):
        if self._init:
            return
        self._init      = True
        self.dataLock   = threading.RLock()
        try:
            with open(DEFAULT_BACKUPFILE,'r') as f:
                self.data = pickle.load(f)
        except (EnvironmentError, pickle.PickleError):
            self.data = {
                'stats' : {},
                'config' : {
                    'solmanagertoken':         DEFAULT_SOLMANAGERTOKEN,
                },
            }
            self._backupData()
    def incrStats(self,statName,step=1):
        with self.dataLock:
            if statName not in self.data['stats']:
                self.data['stats'][statName] = 0
            self.data['stats'][statName] += step
    def getStats(self):
        with self.dataLock:
            return self.data['stats'].copy()
    def getConfig(self,key):
        with self.dataLock:
            return self.data['config'][key]
    def getAllConfig(self):
        with self.dataLock:
            return self.data['config'].copy()
    def setConfig(self,key,value):
        with self.dataLock:
            self.data['config'][key] = value
        self._backupData()
    def _backupData(self):
        with self.dataLock:
            with open(DEFAULT_BACKUPFILE,'w') as f:
                pickle.dump(self.data,f)

class CherryPySSL(bottle.ServerAdapter):
    def run(self, handler):
        from cherrypy import wsgiserver
        from cherrypy.wsgiserver.ssl_pyopenssl import pyOpenSSLAdapter
        server = wsgiserver.CherryPyWSGIServer((self.host, self.port), handler)
        server.ssl_adapter = pyOpenSSLAdapter(
            certificate           = DEFAULT_SOLSERVERCERT,
            private_key           = DEFAULT_SOLSERVERPRIVKEY,
        )
        try:
            server.start()
            log.info("Server started")
        finally:
            server.stop()

class Server(threading.Thread):

    def __init__(self,tcpport):

        # store params
        self.tcpport    = tcpport

        # local variables
        AppData()
        self.sol                  = Sol.Sol()
        self.solmanagertoken      = DEFAULT_SOLMANAGERTOKEN
        self.influxClient         = influxdb.client.InfluxDBClient(
            host        = 'localhost',
            port        = '8086',
            database    = 'realms'
        )
        self.actions    = []

        # initialize web server
        self.web        = bottle.Bottle()
        self.web.route(path=["/<filename>"],
                       method='GET',
                       callback=self._cb_root_GET,
                       name='static')
        self.web.route(path=['/map/<sitename>/<filename>',
                            '/map/<sitename>/',
                            '/map/<sitename>'],
                       method='GET',
                       callback=self._cb_map_GET,
                       name='static')
        self.web.route(path=['/mote/<mac>/'],
                       method='GET',
                       callback=self._cb_graph_GET,
                       name='static')
        self.web.route(path=['/api/v1/jsonp/<site>/<sol_type>/time/<utc_time>'],
                       method='GET',
                       callback=self._cb_jsonp_GET)
        self.web.route(path=['/api/v1/getactions/'],
                       method='GET',
                       callback=self._cb_getactions_GET)
        self.web.route(path=['/api/v1/setaction/<action>/site/<site>/token/<token>'],
                       method='POST',
                       callback=self._cb_setaction_POST)
        self.web.route(path='/api/v1/echo.json',
                       method='POST',
                       callback=self._cb_echo_POST)
        self.web.route(path='/api/v1/status.json',
                       method='GET',
                       callback=self._cb_status_GET)
        self.web.route(path='/api/v1/o.json',
                       method='PUT',
                       callback=self._cb_o_PUT)

        # start the thread
        threading.Thread.__init__(self)
        self.name       = 'Server'
        self.daemon     = True
        self.start()

    def run(self):
        try:
            self.web.run(
                host   = DEFAULT_SOLSERVERHOST,
                port   = self.tcpport,
                server = CherryPySSL,
                quiet  = True,
                debug  = False,
            )

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name,err)

        log.info("Web server started")

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
        self.actions = [] # removing previous actions
        return actions

    #======================== private =========================================

    #=== JSON request handler

    def _cb_root_GET(self, filename="index.html"):
        return bottle.static_file(filename, "www")

    def _cb_graph_GET(self, mac):
        bottle.response.status = 303
        redir_url = "../../grafana/dashboard/db/dynamic?"
        redir_url+= "panelId=1&fullscreen&mac='{1}'".format(mac)
        bottle.redirect(redir_url)

    def _cb_map_GET(self, sitename, filename=""):
        if filename == "":
            return bottle.template("www/map", sitename=sitename)
        else:
            return bottle.static_file(filename, "www")

    def _cb_jsonp_GET(self, site, sol_type, utc_time):
        # clean inputs
        clean = self._check_map_query(site)
        clean = clean and self._check_map_query(sol_type)
        clean = clean and self._check_map_query(utc_time)
        if not clean :
            return "Wrong parameters"

        # build InfluxDB query
        query = "SELECT * FROM " + sol_type
        if site != "all":
            query = query + " WHERE site = '" + site + "'"
        else:
            # select all sites
            query = query + " WHERE site =~ //"
        if sol_type == "SOL_TYPE_DUST_NOTIF_HRNEIGHBORS":
            # compute time - 16min
            start_time = datetime.datetime.strptime(
                        utc_time, '%Y-%m-%dT%H:%M:%S.%fZ') - \
                        datetime.timedelta(minutes=16)
            start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            query = query + " AND time < '" + utc_time + "'"
            query = query + " AND time > '" + start_time + "'"
            query = query + ' GROUP BY "mac" ORDER BY time DESC LIMIT 1'
        elif sol_type == "SOL_TYPE_DUST_SNAPSHOT":
            # compute time - 16min
            start_time = datetime.datetime.strptime(
                        utc_time, '%Y-%m-%dT%H:%M:%S.%fZ') - \
                        datetime.timedelta(minutes=61)
            start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            query = query + " AND time < '" + utc_time + "'"
            query = query + " AND time > '" + start_time + "'"
            query = query + ' GROUP BY "mac" ORDER BY time DESC LIMIT 1'
        elif sol_type == "SOL_TYPE_SOLMANAGER_STATS":
            query = query + ' GROUP BY "mac" ORDER BY time DESC LIMIT 1'
        else:
            query = query + ' GROUP BY "mac" ORDER BY time DESC'

        # send query, parse the result and return the output in json
        influx_json = self.influxClient.query(query).raw
        j = ""
        if len(influx_json) > 0:
            j = self.sol.influxdb_to_json(influx_json)
        return json.dumps(j)

    def _cb_getactions_GET(self):
        """
        Triggered when the solmanager requests the solserver for actions

        Ex:
           1. solmanager asks solserver for actions
           2. solserver tells solmanager to update its SOL library
        """

        global solserver
        try:
            # update stats
            AppData().incrStats(STAT_NUM_JSON_REQ)

            # authorize the client
            site = self._authorizeClient()

            bottle.response.content_type = 'application/json'
            return json.dumps(solserver.get_actions(site))

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name,err)
            raise

    def _cb_setaction_POST(self, action, site, token):
        """
        Add an action to passively give order to the solmanager.
        When the solmanager can't be reached by the solserver, the solmanager
        periodically ask the server for actions.
        """

        global solserver
        try:
            # update stats
            AppData().incrStats(STAT_NUM_SET_ACTION_REQ)

            # authorize the client
            site = self._authorizeClient(token)

            # format action
            action_json = {
                "action":   action,
                "site":     site,
            }

            # add action to list if action is available
            available_actions = ["update"]
            if action in available_actions:
                solserver.set_action(action_json)

            bottle.response.content_type = 'application/json'
            return json.dumps("Action OK")

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name,err)
            raise

    def _cb_echo_POST(self):
        try:
            # update stats
            AppData().incrStats(STAT_NUM_JSON_REQ)

            # authorize the client
            self._authorizeClient()

            bottle.response.content_type = bottle.request.content_type
            return bottle.request.body.read()

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name,err)
            raise

    def _cb_status_GET(self):
        try:
            # update stats
            AppData().incrStats(STAT_NUM_JSON_REQ)

            # authorize the client
            self._authorizeClient()

            returnVal = {
                'version solserver': solserver_version.VERSION,
                'version Sol': SolVersion.VERSION,
                'uptime computer': self._exec_cmd('uptime'),
                'utc': int(time.time()),
                'date': time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime()),
                'last reboot': self._exec_cmd('last reboot'),
                'stats': AppData().getStats()
            }

            bottle.response.content_type = 'application/json'
            return json.dumps(returnVal)

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name,err)
            raise

    def _cb_o_PUT(self):
        try:
            # update stats
            AppData().incrStats(STAT_NUM_JSON_REQ)

            # authorize the client
            authorized_site = self._authorizeClient()

            # abort if malformed JSON body
            if bottle.request.json is None:
                raise bottle.HTTPResponse(
                    body   = json.dumps(
                                {'error': 'Malformed JSON body'}
                            ),
                    status = 400,
                    headers= {'Content-Type': 'application/json'},
                )

            # http->bin
            try:
                sol_binl = self.sol.http_to_bin(bottle.request.json)
            except:
                raise bottle.HTTPResponse(
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
                sol_json          = self.sol.bin_to_json(sol_bin)

                # convert json->influxdb
                tags = self._get_tags(authorized_site, self._formatBuffer(sol_json["mac"]))
                sol_influxdbl    += [self.sol.json_to_influxdb(sol_json,tags)]

            # write to database
            try:
                self.influxClient.write_points(sol_influxdbl)
            except:
                AppData().incrStats(STAT_NUM_OBJECTS_DB_FAIL,1)
                raise
            else:
                AppData().incrStats(STAT_NUM_OBJECTS_DB_OK,)

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name,err)
            raise

    #=== misc

    @staticmethod
    def _get_tags(site_name, mac):
        """
        :param mac str: a dash-separeted mac address
        :return: the tags associated to the given mac address
        :rtype: dict
        Notes: tags are read from 'site.py' file
        """
        return_tags = { "mac" : mac } # default tag is only mac
        for site in sites.SITES:
            if site["name"] == site_name:
                for key,tags in site["motes"].iteritems():
                    if mac == key:
                        return_tags.update(tags)
                        return_tags["site"] = site["name"]
        return return_tags

    @staticmethod
    def _formatBuffer(buf):
        '''
        example: [0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88] -> "11-22-33-44-55-66-77-88"
        '''
        return '-'.join(["%.2x"%i for i in buf])

    def _authorizeClient(self, token=None, site_name=None):
        token_match = False
        if token is None:
            token   = bottle.request.headers.get('X-REALMS-Token')

        for site in sites.SITES:
            if site_name is not None and site_name != site["name"]:
                continue
            if token == site["token"]:
                token_match = True
                site_name = site["name"]

        if not token_match:
            AppData().incrStats(STAT_NUM_JSON_UNAUTHORIZED)
            log.warn("Unauthorized - Invalid Token: %s",token)
            raise bottle.HTTPResponse(
                body   = json.dumps({'error': 'Unauthorized'}),
                status = 401,
                headers= {'Content-Type': 'application/json'},
            )
        else:
            return site_name

    def _exec_cmd(self,cmd):
        returnVal = None
        try:
            returnVal = subprocess.check_output(cmd, shell=False)
        except subprocess.CalledProcessError:
            returnVal = "ERROR"
        return returnVal

    def _check_map_query(self, query):
        OK_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789 _-.:%"
        check = [x for x in query if x.lower() not in OK_CHARS] == []

        # check for wrong keywords
        WRONG_KEYWORDS = ["drop", "insert", "write"]
        for word in WRONG_KEYWORDS:
            if word in query.lower():
                check = False

        return check

#============================ main ============================================

solserver = None

def quitCallback():
    solserver.close()
    log.info("================================== Solserver stopped")

def cli_cb_stats(params):
    stats = AppData().getStats()
    output = []
    for k in sorted(stats.keys()):
        output += ['{0:<30}: {1}'.format(k,stats[k])]
    output = '\n'.join(output)
    print output

def main(tcpport):
    global solserver

    # create the server instance
    solserver = Server(
        tcpport
    )
    log.info("================================== Solserver started")

    # start the CLI interface
    cli = OpenCli.OpenCli(
        "Server",
        solserver_version.VERSION,
        quitCallback,
        [
            ("Sol",SolVersion.VERSION),
        ],
    )
    cli.registerCommand(
        'stats',
        's',
        'print the stats',
        [],
        cli_cb_stats
    )

if __name__ == '__main__':
    # parse the config file
    cf_parser = SafeConfigParser()
    cf_parser.read(DEFAULT_CONFIGFILE)

    if cf_parser.has_section('solmanager'):
        if cf_parser.has_option('solmanager','token'):
            DEFAULT_SOLMANAGERTOKEN = cf_parser.get('solmanager','token')

    if cf_parser.has_section('solserver'):
        if cf_parser.has_option('solserver','host'):
            DEFAULT_SOLSERVER = cf_parser.get('solserver','host')
        if cf_parser.has_option('solserver','tcpport'):
            DEFAULT_TCPPORT = cf_parser.getint('solserver','tcpport')
        if cf_parser.has_option('solserver','certfile'):
            DEFAULT_SOLSERVERCERT = cf_parser.get('solserver','certfile')
        if cf_parser.has_option('solserver','privatekey'):
            DEFAULT_SOLSERVERPRIVKEY = cf_parser.get('solserver','privatekey')
        if cf_parser.has_option('solserver','backupfile'):
            DEFAULT_BACKUPFILE = cf_parser.get('solserver','backupfile')
    log.debug("Configuration:\n" +\
            "\tSOL_SERVER_HOST: '%s'\n"             +\
            "\tDEFAULT_TCPPORT: %d\n"               +\
            "\tDEFAULT_SOLSERVERCERT:  '%s'\n"      +\
            "\tDEFAULT_SOLSERVERPRIVKEY: '%s'\n"    +\
            "\tDEFAULT_BACKUPFILE: '%s'\n"          ,
            DEFAULT_SOLSERVER,
            DEFAULT_TCPPORT,
            DEFAULT_SOLSERVERCERT,
            DEFAULT_SOLSERVERPRIVKEY,
            DEFAULT_BACKUPFILE
            )

    # parse the command line
    parser = OptionParser("usage: %prog [options]")
    parser.add_option(
        "-t", "--tcpport", dest="tcpport",
        default=DEFAULT_TCPPORT,
        help="TCP port to start the JSON API on."
    )
    (options, args) = parser.parse_args()

    main(
        options.tcpport,
    )
