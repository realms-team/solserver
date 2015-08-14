#!/usr/bin/python

#============================ adjust path =====================================

import sys
import os

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'Sol'))

#============================ imports =========================================

import json
import threading
from   optparse import OptionParser

import OpenCli

import bottle
import Sol
import SolVersion
import server_version

#============================ defines =========================================

DEFAULT_TCPPORT    = 8080

#============================ body ============================================

class Server(threading.Thread):
    
    def __init__(self,tcpport):
        
        # store params
        self.tcpport    = tcpport
        
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
        self.web.run(
            host   = 'localhost',
            port   = self.tcpport,
            quiet  = True,
            debug  = False,
        )
    
    #======================== public ==========================================
    
    def close(self):
        print 'TODO Server.close()'
    
    #======================== private =========================================
    
    #=== JSON request handler
    
    def _cb_echo_POST(self):
        bottle.response.status = 501
        bottle.response.content_type = 'application/json'
        return json.dumps({'error': 'Not Implemented yet :-('})
    
    def _cb_status_GET(self):
        bottle.response.status = 501
        bottle.response.content_type = 'application/json'
        return json.dumps({'error': 'Not Implemented yet :-('})
    
    def _cb_o_PUT(self):
        bottle.response.status = 501
        bottle.response.content_type = 'application/json'
        return json.dumps({'error': 'Not Implemented yet :-('})

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
            (
                "Sol",
                (
                    SolVersion.SOL_VERSION['SOL_VERSION_MAJOR'],
                    SolVersion.SOL_VERSION['SOL_VERSION_MINOR'],
                    SolVersion.SOL_VERSION['SOL_VERSION_PATCH'],
                    SolVersion.SOL_VERSION['SOL_VERSION_BUILD'],
                ),
            ),
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
