#!/usr/bin/python

#============================ adjust path =====================================

import sys
import os
if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', 'Sol'))
    
#============================ imports =========================================

from   optparse                             import OptionParser

import SolVersion
import server_version
import OpenCli

#============================ defines =========================================

DEFAULT_PORT = 8080

#============================ body ============================================

class Server(object):
    
    def __init__(self,port):
        pass
    
    #======================== public ==========================================
    
    #======================== private =========================================


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
