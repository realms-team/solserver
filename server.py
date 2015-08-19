#!/usr/bin/python

#============================ adjust path =====================================

import sys
import os

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'Sol'))

#============================ imports =========================================

import pickle
import time
import json
import subprocess
import threading
from   optparse import OptionParser

import OpenCli

import bottle
import Sol
import SolVersion
import server_version

#============================ defines =========================================

DEFAULT_TCPPORT              = 8081

DEFAULT_BACKUPFILE           = 'server.backup'
# config file
DEFAULT_SERVERTOKEN          = 'DEFAULT_SERVERTOKEN'
DEFAULT_BASESTATIONTOKEN     = 'DEFAULT_BASESTATIONTOKEN'

#============================ helpers =========================================

def printCrash(threadName):
    import traceback
    output  = []
    output += ["CRASH in Thread {0}!".format(threadName)]
    output += [traceback.format_exc()]
    output  = '\n'.join(output)
    print output

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
                    'servertoken':          DEFAULT_SERVERTOKEN,
                    'basestationtoken':     DEFAULT_BASESTATIONTOKEN,
                },
            }
            self._backupData()
    def incrStats(self,statName):
        with self.dataLock:
            if statName not in self.data['stats']:
                self.data['stats'][statName] = 0
            self.data['stats'][statName] += 1
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
    # to generate a certificate/private_key using OpenSSL:
    # openssl genrsa -out server.ppk 1024
    # openssl req -new -x509 -key server.ppk -out server.cert -days 1825
    def run(self, handler):
        from cherrypy import wsgiserver
        from cherrypy.wsgiserver.ssl_pyopenssl import pyOpenSSLAdapter
        server = wsgiserver.CherryPyWSGIServer((self.host, self.port), handler)
        server.ssl_adapter = pyOpenSSLAdapter(
            certificate           = "server.cert",
            private_key           = "server.ppk",
        )
        try:
            server.start()
        finally:
            server.stop()

class Server(threading.Thread):
    
    STAT_NUM_REQ_RX = 'NUM_REQ_RX'
    
    def __init__(self,tcpport):
        
        # store params
        self.tcpport    = tcpport
        
        # local variables
        AppData()
        self.sol                  = Sol.Sol()
        self.servertoken          = DEFAULT_SERVERTOKEN # TODO: read from file
        self.basestationtoken     = DEFAULT_BASESTATIONTOKEN # TODO: read from file
        
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
                host   = 'localhost',
                port   = self.tcpport,
                server = CherryPySSL,
                quiet  = True,
                debug  = False,
            )
        except:
            printCrash(self.name)
    
    #======================== public ==========================================
    
    def close(self):
        # bottle thread is daemon, it will close when main thread closes
        pass
    
    #======================== private =========================================
    
    #=== JSON request handler
    
    def _cb_root_GET(self):
        return 'It works!'
    
    def _cb_echo_POST(self):
        self._authorizeClient()
        try:
            # increment stats
            AppData().incrStats(self.STAT_NUM_REQ_RX)
            
            bottle.response.content_type = bottle.request.content_type
            return bottle.request.body.read()
           
        except Exception as err:
            printCrash(self.name)
            raise
    
    def _cb_status_GET(self):
        self._authorizeClient()
        try:
            # increment stats
            AppData().incrStats(self.STAT_NUM_REQ_RX)
            
            returnVal = {}
            returnVal['version server']   = server_version.VERSION
            returnVal['version Sol']      = SolVersion.VERSION
            returnVal['uptime computer']  = self._exec_cmd('uptime')
            returnVal['utc']              = int(time.time())
            returnVal['date']             = time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime())
            returnVal['last reboot']      = self._exec_cmd('last reboot')
            returnVal['stats']            = AppData().getStats()
            
            bottle.response.content_type = 'application/json'
            return json.dumps(returnVal)
            
        except Exception as err:
            printCrash(self.name)
            raise
    
    def _cb_o_PUT(self):
        self._authorizeClient()
        try:
            # increment stats
            AppData().incrStats(self.STAT_NUM_REQ_RX)
            
            # abort if malformed JSON body
            if bottle.request.json==None:
                raise bottle.HTTPResponse(
                    body   = json.dumps({'error': 'Malformed JSON body'}),
                    status = 400,
                    headers= {'Content-Type': 'application/json'},
                )
            
            # parse dicts
            try:
                dicts = self.sol.json_to_dicts(bottle.request.json)
            except:
                raise bottle.HTTPResponse(
                    body   = json.dumps({'error': 'Malformed JSON body contents'}),
                    status = 400,
                    headers= {'Content-Type': 'application/json'},
                )
            
            # publish contents
            print 'TODO: _cb_o_PUT publish {0} objects'.format(len(dicts))
            
        except Exception as err:
            printCrash(self.name)
            raise
    
    #=== misc
    
    def _authorizeClient(self):
        if bottle.request.headers.get('X-REALMS-Token')!=self.servertoken:
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

server = None

def quitCallback():
    global server
    
    server.close()

def main(tcpport):
    global server
    
    # create the server instance
    server = Server(
        tcpport
    )
    
    # start the CLI interface
    OpenCli.OpenCli(
        "Server",
        server_version.VERSION,
        quitCallback,
        [
            ("Sol",SolVersion.VERSION),
        ],
    )

if __name__ == '__main__':
    
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
