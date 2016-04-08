#!/usr/bin/python

# =========================== adjust path =====================================

import sys
import os

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'sol'))

# =========================== imports =========================================

import pickle
import time
import json
import subprocess
import threading
import traceback
from   optparse                 import OptionParser
from   ConfigParser             import SafeConfigParser

import influxdb
import bottle

import OpenCli
import Sol
import SolVersion
import SolDefines
import solserver_version
import flatdict
import datetime

#============================ defines =========================================

DEFAULT_TCPPORT              = 8081
DEFAULT_SOLSERVERHOST        = '0.0.0.0'  # listten on all interfaces

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
    output += ["==============================================================="]
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
    with open(DEFAULT_CRASHLOG,'a') as f:
        f.write(output)

def o_to_influx(dicts):
    '''
        Transform list of Sol Objects to list of InfluxDB points
        Args: dicts (list) list of dictionaries
        Returns: idicts (list) list of converted dictionaries
        Exemple:
            dicts = {
                "timestamp" : 1455202067
                "mac" : [ 0, 23, 13, 0, 0, 56, 0, 99 ]
                "type" 14
                "value" : [ 240, 185, 240, 185, 0, 0 ]
            }
    '''
    idicts = []

    for obj in dicts:
        iobj = {}

        # get SOL type name
        type_name = SolDefines.solTypeToString(SolDefines,obj['type'])

        # (temporary) only keep DUST types
        if type_name.startswith('SOL_TYPE_DUST') and getattr(SolDefines,type_name)==obj['type']:

            iobj = {
                # convert timestamp to UTC
                "time" : datetime.datetime.utcfromtimestamp(obj['timestamp']),

                # change type name
                "measurement" : SolDefines.solTypeToString(SolDefines,obj['type']),

                # tags
                "tags" : {
                    "mac" : '-'.join(["{0:02x}".format(i) for i in obj['mac']])
                },

                # populate fields
                "fields" : flatdict.FlatDict(obj['value'])
            }

            # append element to list
            idicts.append(iobj)

    return idicts

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
        except:
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
                                            host='localhost',
                                            port='8086',
                                            database='realms'
                                        )
        
        # initialize web server
        self.web        = bottle.Bottle()
        #self.web.route(path='/',                   method='GET', callback=self._cb_root_GET)
        self.web.route(path='/api/v1/echo.json',   method='POST',callback=self._cb_echo_POST)
        self.web.route(path='/api/v1/status.json', method='GET', callback=self._cb_status_GET)
        self.web.route(path='/api/v1/o.json',      method='PUT', callback=self._cb_o_PUT)
        
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
    
    #======================== public ==========================================
    
    def close(self):
        # bottle thread is daemon, it will close when main thread closes
        pass
    
    #======================== private =========================================
    
    #=== JSON request handler
    
    def _cb_root_GET(self):
        return 'It works!'
    
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
                    body   = json.dumps({'error': 'Malformed JSON body'}),
                    status = 400,
                    headers= {'Content-Type': 'application/json'},
                )

            # parse dicts
            try:
                dicts = self.sol.contenttype_to_bin(bottle.request.json)
            except:
                raise bottle.HTTPResponse(
                    body   = json.dumps({'error': 'Malformed JSON body contents'}),
                    status = 400,
                    headers= {'Content-Type': 'application/json'},
                )

            # parse objects values
            for obj in dicts:
                obj['value'] = self.sol.unpack_obj_value(obj['type'],*obj['value'])

            # transform Sol Objects into InfluxDB points
            idicts = o_to_influx(dicts)

            # publish contents
            try:
                self.influxClient.write_points(idicts)
            except:
                AppData().incrStats(STAT_NUM_OBJECTS_DB_FAIL,len(dicts))
                raise
            else:
                AppData().incrStats(STAT_NUM_OBJECTS_DB_OK,len(dicts))

        except bottle.BottleException:
            raise

        except Exception as err:
            logCrash(self.name,err)
            raise
    
    #=== misc
    
    def _authorizeClient(self):
        if bottle.request.headers.get('X-REALMS-Token')!=self.solservertoken:
            AppData().incrStats(STAT_NUM_JSON_UNAUTHORIZED)
            raise bottle.HTTPResponse(
                body   = json.dumps({'error': 'Unauthorized'}),
                status = 401,
                headers= {'Content-Type': 'application/json'},
            )
    
    def _exec_cmd(self,cmd):
        returnVal = None
        try:
            returnVal = subprocess.check_output(cmd, shell=False)
        except:
            returnVal = "ERROR"
        return returnVal
    
#============================ main ============================================

solserver = None

def quitCallback():
    global solserver
    
    solserver.close()

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
        if cf_parser.has_option('solserver','crashlogfile'):
            DEFAULT_CRASHLOG = cf_parser.get('solserver','crashlogfile')
        if cf_parser.has_option('solserver','backupfile'):
            DEFAULT_BACKUPFILE = cf_parser.get('solserver','backupfile')

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
