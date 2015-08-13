#!/usr/bin/python

#============================ adjust path =====================================

import sys
import os
import json

import threading

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'Sol'))
    
#============================ imports =========================================

from   optparse                             import OptionParser

import bottle

import SolVersion
import server_version
import OpenCli

#============================ defines =========================================

DEFAULT_PORT = 8080

#============================ body ============================================

class Server(object):
    
    def __init__(self,port):
        
        # local variables
        self.web = bottle.Bottle()
        
        # initialize routes
        self.web.route(path='/api/v1/echo.json',   method='GET', callback=self._webcb_echo_GET)
        self.web.route(path='/api/v1/status.json', method='GET', callback=self._webcb_status_GET)
        self.web.route(path='/api/v1/o.json',      method='PUT', callback=self._webcb_o_PUT)
        
        # start web server in separate thread
        self.webThread = threading.Thread(
            target = self.web.run,
            kwargs = {
                'host'          : 'localhost',
                'port'          : port,
                'quiet'         : True,
                'debug'         : False,
            }
        )
        self.webThread.start()
    
    #======================== public ==========================================
    
    #======================== private =========================================
    
    def _webcb_echo_GET(self):
        bottle.response.status = 501
        bottle.response.content_type = 'application/json'
        return json.dumps({'error': 'Not Implemented yet :-('})
    
    def _webcb_status_GET(self):
        bottle.response.status = 501
        bottle.response.content_type = 'application/json'
        return json.dumps({'error': 'Not Implemented yet :-('})
    
    def _webcb_o_PUT(self):
        bottle.response.status = 501
        bottle.response.content_type = 'application/json'
        return json.dumps({'error': 'Not Implemented yet :-('})

#============================ main ============================================

def quitCallback():
    print "TODO quitCallback"

def main(port):
    
    # create the server instance
    server = Server(port)
    
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

#============================ main ============================================

if __name__ == '__main__':
    
    # parse the command line
    parser = OptionParser("usage: %prog [options]")
    parser.add_option("-p", "--port", dest="port", 
                      default=DEFAULT_PORT,
                      help="TCP port to listen on")
    (options, args) = parser.parse_args()
    
    main(options.port)
