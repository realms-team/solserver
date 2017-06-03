#!/usr/bin/python

# =========================== adjust path =====================================

import sys
import os

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'sol'))
    sys.path.insert(0, os.path.join(here, '..', 'smartmeshsdk','libs'))

# =========================== imports =========================================

# from default Python
import time
import json
import subprocess
import threading
import traceback
import ConfigParser
import logging.config
import datetime
import sites

# third-party packages
import OpenSSL
import bottle
import influxdb

# project-specific
import solserver_version
from   dustCli               import DustCli
from   solobjectlib          import Sol, \
                                    SolVersion

                                    

#============================ logging =========================================

logging.config.fileConfig('logging.conf')
log = logging.getLogger('solserver')
log.setLevel(logging.DEBUG)

#============================ defines =========================================

CONFIGFILE                   = 'solserver.config'

#============================ helpers =========================================

def logCrash(threadName, err):
    output  = []
    output += ["============================================================="]
    output += [time.strftime("%m/%d/%Y %H:%M:%S UTC", time.gmtime())]
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

#======== singletons

class AppConfig(object):
    """
    Singleton which contains the configuration of the application.
    
    Configuration is read once from file CONFIGFILE
    """
    _instance = None
    _init     = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AppConfig, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if self._init:
            return
        self._init = True

        # local variables
        self.dataLock   = threading.RLock()
        self.config     = {}

        config          = ConfigParser.ConfigParser()
        config.read(CONFIGFILE)

        with self.dataLock:
            for (k,v) in config.items('solserver'):
                try:
                    self.config[k] = float(v)
                except ValueError:
                    try:
                        self.config[k] = int(v)
                    except ValueError:
                        self.config[k] = v

    def get(self,name):
        with self.dataLock:
            return self.config[name]

class AppStats(object):
    """
    Singleton which contains the stats of the application.
    
    Stats are read once from file STATSFILE.
    """
    _instance = None
    _init     = False

    ALLSTATS  = [
        'NUM_JSON_REQ',
        'NUM_JSON_UNAUTHORIZED',
        'NUM_CRASHES',
        'STAT_NUM_OBJECTS_DB_OK',
        'STAT_NUM_OBJECTS_DB_FAIL',
        'NUM_SET_ACTION_REQ',
    ]
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AppStats, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if self._init:
            return
        self._init      = True
        
        self.dataLock   = threading.RLock()
        self.stats      = {}
        try:
            with open(STATSFILE, 'r') as f:
                for line in f:
                    k        = line.split('=')[0].strip()
                    v        = line.split('=')[1].strip()
                    try:
                        v    = int(v)
                    except ValueError:
                        pass
                    self.stats[k] = v
                log.info("Stats recovered from file.")
        except (EnvironmentError, EOFError) as e:
            log.info("Could not read stats file: %s", e)
            self._backup()
    
    
    # ======================= public ==========================================
    
    def increment(self, statName):
        self._validateStatName(statName)
        with self.dataLock:
            if statName not in self.stats:
                self.stats[statName] = 0
            self.stats[statName] += 1
        self._backup()

    def update(self, k, v):
        self._validateStatName(k)
        with self.dataLock:
            self.stats[k] = v
        self._backup()

    def get(self):
        with self.dataLock:
            stats = self.stats.copy()
        stats['PUBFILE_BACKLOG']   = PubFileThread().getBacklogLength()
        stats['PUBSERVER_BACKLOG'] = PubServerThread().getBacklogLength()
        return stats

    # ======================= private =========================================

    def _validateStatName(self, statName):
        if statName.startswith("NUMRX_")==False:
            assert statName in self.ALLSTATS

    def _backup(self):
        with self.dataLock:
            output = ['{0} = {1}'.format(k,v) for (k,v) in self.stats.items()]
            output = '\n'.join(output)
            with open(STATSFILE, 'w') as f:
                f.write(output)

#======== JSON API to receive notifications from SolManager

class JsonApiThread(threading.Thread):
    
    class HTTPSServer(bottle.ServerAdapter):
        def run(self, handler):
            from cheroot.wsgi import Server as WSGIServer
            from cheroot.ssl.pyopenssl import pyOpenSSLAdapter
            server = WSGIServer((self.host, self.port), handler)
            server.ssl_adapter = pyOpenSSLAdapter(
                certificate = AppConfig().get('solserver_certificate'),
                private_key = AppConfig().get('solserver_private_key'),
            )
            try:
                server.start()
                log.info("Server started")
            finally:
                server.stop()
    
    def __init__(self):

        # local variables
        self.sol                  = Sol.Sol()
        self.influxClient         = influxdb.client.InfluxDBClient(
            host        = AppConfig().get('inlfuxdb_host'),
            port        = AppConfig().get('inlfuxdb_port'),
            database    = AppConfig().get('inlfuxdb_database'),
        )
        self.actions    = []

        # initialize web server
        self.web        = bottle.Bottle()
        self.web.route(
            path        = "/<filename>",
            method      = 'GET',
            callback    = self._webhandle_root_GET,
        )
        self.web.route(
            path        = [
                '/map/<sitename>/<filename>',
                '/map/<sitename>/',
                '/map/<sitename>',
            ],
            method      = 'GET',
            callback    = self._webhandle_map_GET,
        )
        self.web.route(
            path        = '/mote/<mac>/',
            method      = 'GET',
            callback    = self._cb_graph_GET,
        )
        self.web.route(
            path        = '/api/v1/jsonp/<site>/<sol_type>/time/<utc_time>',
            method      = 'GET',
            callback    = self._cb_jsonp_GET
        )
        self.web.route(
            path        = '/api/v1/getactions/',
            method      = 'GET',
            callback    = self._cb_getactions_GET,
        )
        self.web.route(
            path        = '/api/v1/setaction/<action>/site/<site>/token/<token>',
            method      = 'POST',
            callback    = self._cb_setaction_POST,
        )
        self.web.route(
            path        = '/api/v1/echo.json',
            method      = 'POST',
            callback    = self._cb_echo_POST,
        )
        self.web.route(
            path        = '/api/v1/status.json',
            method      = 'GET',
            callback    = self._cb_status_GET,
        )
        self.web.route(
            path        = '/api/v1/o.json',
            method      = 'PUT',
            callback    = self._cb_o_PUT,
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
                port   = AppConfig().get('solserver_tcpport'),
                server = self.HTTPSServer,
                quiet  = True,
                debug  = False,
            )

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name, err)

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

    def _webhandle_root_GET(self, filename="index.html"):
        return bottle.static_file(filename, "www")

    def _cb_graph_GET(self, mac):
        bottle.response.status = 303
        redir_url  = "../../grafana/dashboard/db/dynamic?"
        redir_url += "panelId=1&fullscreen&mac='{0}'".format(mac)
        bottle.redirect(redir_url)

    def _webhandle_map_GET(self, sitename, filename=""):
        if filename == "":
            return bottle.template("www/map", sitename=sitename)
        else:
            return bottle.static_file(filename, "www")

    def _cb_jsonp_GET(self, site, sol_type, utc_time):
        # clean inputs
        clean = self._check_map_query(site)
        clean = clean and self._check_map_query(sol_type)
        clean = clean and self._check_map_query(utc_time)
        if not clean:
            return "Wrong parameters"

        # build InfluxDB query
        query = "SELECT * FROM " + sol_type
        if site != "all":
            query += " WHERE site = '" + site + "'"
        else:
            # select all sites
            query += " WHERE site =~ //"
        if sol_type == "SOL_TYPE_DUST_NOTIF_HRNEIGHBORS":
            # compute time - 16min
            start_time = datetime.datetime.strptime(
                        utc_time, '%Y-%m-%dT%H:%M:%S.%fZ') - \
                        datetime.timedelta(minutes=16)
            start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            query += " AND time < '" + utc_time + "'"
            query += " AND time > '" + start_time + "'"
            query += ' GROUP BY "mac" ORDER BY time DESC LIMIT 1'
        elif sol_type == "SOL_TYPE_DUST_SNAPSHOT":
            # compute time - 16min
            start_time = datetime.datetime.strptime(
                        utc_time, '%Y-%m-%dT%H:%M:%S.%fZ') - \
                        datetime.timedelta(minutes=61)
            start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            query += " AND time < '" + utc_time + "'"
            query += " AND time > '" + start_time + "'"
            query += ' GROUP BY "mac" ORDER BY time DESC LIMIT 1'
        elif sol_type == "SOL_TYPE_SOLMANAGER_STATS":
            query += ' GROUP BY "mac" ORDER BY time DESC LIMIT 1'
        else:
            query += ' GROUP BY "mac" ORDER BY time DESC'

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
            logCrash(self.name, err)
            raise

    def _cb_setaction_POST(self, action, site, token):
        """
        Add an action to passively give order to the solmanager.
        When the solmanager can't be reached by the solserver, the solmanager
        periodically ask the server for actions.
        """

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
            logCrash(self.name, err)
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
            logCrash(self.name, err)
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
            logCrash(self.name, err)
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
                sol_influxdbl    += [self.sol.json_to_influxdb(sol_json, tags)]

            # write to database
            try:
                self.influxClient.write_points(sol_influxdbl)
            except:
                AppData().incrStats(STAT_NUM_OBJECTS_DB_FAIL, 1)
                raise
            else:
                AppData().incrStats(STAT_NUM_OBJECTS_DB_OK,)

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name, err)
            raise

    #=== misc

    @staticmethod
    def _get_tags(site_name, mac):
        """
        :param str mac : a dash-separated mac address
        :return: the tags associated to the given mac address
        :rtype: dict
        Notes: tags are read from 'site.py' file
        """
        return_tags = {"mac": mac}  # default tag is only mac
        for site in sites.SITES:
            if site["name"] == site_name:
                for key, tags in site["motes"].iteritems():
                    if mac == key:
                        return_tags.update(tags)
                        return_tags["site"] = site["name"]
        return return_tags

    @staticmethod
    def _formatBuffer(buf):
        """
        example: [0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88] -> "11-22-33-44-55-66-77-88"
        """
        return '-'.join(["%.2x" %i for i in buf])

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
            log.warn("Unauthorized - Invalid Token: %s", token)
            raise bottle.HTTPResponse(
                body   = json.dumps({'error': 'Unauthorized'}),
                status = 401,
                headers= {'Content-Type': 'application/json'},
            )
        else:
            return site_name

    def _exec_cmd(self, cmd):
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

#======== main application thread

class SolServer(object):

    def __init__(self):

        # API thread
        self.jsonApiThread  = JsonApiThread()

        # CLI interface
        self.cli            = DustCli.DustCli("SolServer",self._clihandle_quit)
        self.cli.registerCommand(
            name                       = 'stats',
            alias                      = 's',
            description                = 'print the stats',
            params                     = [],
            callback                   = self._clihandle_stats,
        )
        self.cli.start()

    def _clihandle_quit(self):
        time.sleep(.3)
        print "bye bye."
        # all threads as daemonic, will close automatically
    
    def _clihandle_stats(self,params):
        stats = AppData().getStats()
        output = []
        for k in sorted(stats.keys()):
            output += ['{0:<30}: {1}'.format(k, stats[k])]
        output = '\n'.join(output)
        print output

#============================ main ============================================

def main():
    solServer = SolServer()

if __name__ == '__main__':
    main()
