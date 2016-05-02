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
import Sol
import SolVersion
import solserver_version

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

DEFAULT_SOLSERVERTOKEN       = 'DEFAULT_SOLSERVERTOKEN'
DEFAULT_SOLMANAGERTOKEN      = 'DEFAULT_SOLMANAGERTOKEN'
DEFAULT_SOLSERVERCERT        = 'solserver.cert'
DEFAULT_SOLSERVERPRIVKEY     = 'solserver.ppk'

# stats

STAT_NUM_JSON_REQ            = 'NUM_JSON_REQ'
STAT_NUM_JSON_UNAUTHORIZED   = 'NUM_JSON_UNAUTHORIZED'
STAT_NUM_CRASHES             = 'NUM_CRASHES'
STAT_NUM_OBJECTS_DB_OK       = 'STAT_NUM_OBJECTS_DB_OK'
STAT_NUM_OBJECTS_DB_FAIL     = 'STAT_NUM_OBJECTS_DB_FAIL'

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
                    'solservertoken':          DEFAULT_SOLSERVERTOKEN,
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
        self.solservertoken       = DEFAULT_SOLSERVERTOKEN
        self.solmanagertoken      = DEFAULT_SOLSERVERTOKEN
        self.influxClient         = influxdb.client.InfluxDBClient(
            host        = 'localhost',
            port        = '8086',
            database    = 'realms'
        )

        # initialize web server
        self.web        = bottle.Bottle()
        self.web.route(path=['/<filename>',"/"],
                       method='GET',
                       callback=self._cb_root_GET,
                       name='static')
        self.web.route(path=['/api/v1/jsonp/<site>/<sol_type>/time/<utc_time>'],
                       method='GET',
                       callback=self._cb_jsonp_GET)
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

    #======================== private =========================================

    #=== JSON request handler

    def _cb_root_GET(self, filename="map.html"):
        return bottle.static_file(filename, "www")

    def _cb_jsonp_GET(self, site, sol_type, utc_time):
        # clean inputs
        clean = self._check_map_query(site)
        clean = clean and self._check_map_query(sol_type)
        clean = clean and self._check_map_query(utc_time)
        if not clean :
            return "Wrong parameters"

        # compute time + 30m
        end_time = datetime.datetime.strptime(
                        utc_time,
                        '%Y-%m-%dT%H:%M:%S.%fZ'
                    ) + datetime.timedelta(minutes=31)
        end_time = end_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # build InfluxDB query
        query = "SELECT * FROM " + sol_type
        if sol_type == "SOL_TYPE_DUST_NOTIF_HRNEIGHBORS":
            query = query + " WHERE time > '" + utc_time
            query = query + "' AND time < '" + end_time + "'"
            query = query + " AND site='" + site + "'"
        else:
            query = query + " WHERE site='" + site + "'"

        # send query, parse the result and return the output in json
        influx_json = self.influxClient.query(query).raw
        j = ""
        if len(influx_json) > 0:
            j = self.sol.influxdb_to_json(influx_json)
        return json.dumps(j)

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
            self._authorizeClient()

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

                # convert bin->json->influxdb
                sol_json          = self.sol.bin_to_json(sol_bin)
                sol_influxdbl    += [self.sol.json_to_influxdb(sol_json)]

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

    def _authorizeClient(self):
        if bottle.request.headers.get('X-REALMS-Token')!=self.solservertoken:
            AppData().incrStats(STAT_NUM_JSON_UNAUTHORIZED)
            log.warn("Unauthorized - Invalid Token: %s",
                    bottle.request.headers.get('X-REALMS-Token'))
            raise bottle.HTTPResponse(
                body   = json.dumps({'error': 'Unauthorized'}),
                status = 401,
                headers= {'Content-Type': 'application/json'},
            )

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
        if cf_parser.has_option('solserver','token'):
            DEFAULT_SOLSERVERTOKEN = cf_parser.get('solserver','token')
        if cf_parser.has_option('solserver','certfile'):
            DEFAULT_SOLSERVERCERT = cf_parser.get('solserver','certfile')
        if cf_parser.has_option('solserver','privatekey'):
            DEFAULT_SOLSERVERPRIVKEY = cf_parser.get('solserver','privatekey')
        if cf_parser.has_option('solserver','backupfile'):
            DEFAULT_BACKUPFILE = cf_parser.get('solserver','backupfile')
    log.debug("Configuration:\n" +\
            "\tSOL_SERVER_HOST: '%s'\n"             +\
            "\tDEFAULT_TCPPORT: %d\n"               +\
            "\tDEFAULT_SOLSERVERTOKEN: '%s'\n"      +\
            "\tDEFAULT_SOLSERVERCERT:  '%s'\n"      +\
            "\tDEFAULT_SOLSERVERPRIVKEY: '%s'\n"    +\
            "\tDEFAULT_BACKUPFILE: '%s'\n"          ,
            DEFAULT_SOLSERVER,
            DEFAULT_TCPPORT,
            DEFAULT_SOLSERVERTOKEN,
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
