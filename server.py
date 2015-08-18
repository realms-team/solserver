#!/usr/bin/python

#============================ adjust path =====================================

import sys
import os

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'Sol'))

#============================ imports =========================================

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

DEFAULT_TCPPORT              = 8080
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

class Stats(object):
    _instance = None
    _init     = False
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Stats,cls).__new__(cls, *args, **kwargs)
        return cls._instance
    def __init__(self):
        if self._init:
            return
        self._init    = True
        self.dataLock = threading.RLock()
        self.data     = {}
    def incr(self,statName):
        with self.dataLock:
            if statName not in self.data:
                self.data[statName] = 0
            self.data[statName] += 1
    def get(self):
        with self.dataLock:
            return self.data.copy()

class Server(threading.Thread):
    
    STAT_NUM_REQ_RX = 'NUM_REQ_RX'
    
    def __init__(self,tcpport):
        
        # store params
        self.tcpport    = tcpport
        
        # local variables
        self.sol                  = Sol.Sol()
        self.servertoken          = DEFAULT_SERVERTOKEN # TODO: read from file
        self.basestationtoken     = DEFAULT_BASESTATIONTOKEN # TODO: read from file
        
        # initialize web server
        self.web        = bottle.Bottle()
        self.web.route(path='/api/v1/echo.json',   method='POST',callback=self._cb_echo_POST)
        self.web.route(path='/api/v1/status.json', method='GET', callback=self._cb_status_GET)
        self.web.route(path='/api/v1/o.json',      method='PUT', callback=self._cb_o_PUT)
        
        # start the thread
        threading.Thread.__init__(self)
        self.name       = 'Server'
        self.start()
    
    def run(self):
        try:
            self.web.run(
                host   = 'localhost',
                port   = self.tcpport,
                quiet  = True,
                debug  = False,
            )
        except:
            printCrash(self.name)
    
    #======================== public ==========================================
    
    def close(self):
        # TODO: implement (#4)
        print 'TODO Server.close()'
    
    #======================== private =========================================
    
    #=== JSON request handler
    
    def _cb_echo_POST(self):
        Stats().incr(self.STAT_NUM_REQ_RX)
        bottle.response.content_type = bottle.request.content_type
        return bottle.request.body.read()
    
    def _cb_status_GET(self):
        Stats().incr(self.STAT_NUM_REQ_RX)
        
        returnVal = {}
        returnVal['version server']   = server_version.VERSION
        returnVal['version Sol']      = SolVersion.VERSION
        returnVal['uptime computer']  = self._exec_cmd('uptime')
        returnVal['utc']              = int(time.time())
        returnVal['date']             = time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime())
        returnVal['last reboot']      = self._exec_cmd('last reboot')
        returnVal['stats']            = Stats().get()
        
        bottle.response.content_type = 'application/json'
        return json.dumps(returnVal)
    
    def _cb_o_PUT(self):
        try:
            Stats().incr(self.STAT_NUM_REQ_RX)
            
            # abort if not right token
            if bottle.request.headers.get('X-REALMS-Token')!=self.servertoken:
                bottle.response.status = 401
                bottle.response.content_type = 'application/json'
                return json.dumps({'error': 'Unauthorized'})
            
            # abort if malformed JSON body
            if bottle.request.json==None:
                bottle.response.status = 400
                bottle.response.content_type = 'application/json'
                return json.dumps({'error': 'Malformed JSON body'})
            
            # parse dicts
            try:
                dicts = self.sol.json_to_dicts(bottle.request.json)
            except:
                bottle.response.status = 400
                bottle.response.content_type = 'application/json'
                return json.dumps({'error': 'Malformed JSON body contents'})
            
            # publish contents
            print 'TODO: _cb_o_PUT publish'
            
        except Exception as err:
            printCrash(self.name)
            raise
    
    #=== misc
    
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
