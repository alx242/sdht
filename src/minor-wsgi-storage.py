#! /usr/bin/python
# -*- mode: python -*-

from wsgiref.simple_server import make_server
from bsddb import db
from optparse import OptionParser

import cgi, cgitb, sys, traceback
import urllib, urllib2

_local_db = None
_available = True

def storage_app(environ, start_response):
    """
    The actual WSGI storage application.

    The one thing required from the 'accessor' is the command form
    part which handles the flow.

    These commands are available:
    * 'check' - Check if this storage is available or not.
    
    * 'set' - Simple setting of a key/value in the Berkeley DB.
    Needs these extra parts:
    'key' - A string hashed key
    'value' - A serialized value
          
    * 'get' - Simple getting of a value in the Berkeley DB based on a key.
    Needs these extra parts:
    'key' - A string hashed key
    
    * 'transfer_part' - Transfer a choosen part of the Berkeley DB from this storage to another storage.
    Needs these extra parts:
    'other_node_ip' - IP of other node
    'other_node_port' - Port of other node
    'from_key_id' - Starting hash key to transfer
    'to_key_id' - Ending hash key to transfer

    * 'transfer' - Transfer the complete Berkeley DB to another storage and make this storage unavailable.
    Needs these extra parts:
    'other_node_ip' - IP of other node
    'other_node_port' - Port of other node
    """
    
    global _local_db, _available
    status = '200 OK'
    response_headers = [('Content-type','text/plain')]
    start_response(status, response_headers)

    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ, keep_blank_values=True)

    # Global post parts
    command = form.getfirst("cmd", "")
    key = form.getfirst("key", "")
    value = form.getfirst("value", "")
    
    print "Executing command '%s' on server which is available? %s" % (command, _available)

    if not _available:
        return []
    
    if command == "set" and key and value:
        # Simple set value command
        print "Setting key: ", key
        _local_db.put(key, value)
        return ['OK']

    elif command == "check":
        # Check if storage is available
        if _available:
            return ['OK']
        
    elif command == "get" and key:
        # Simple get command
        data = _local_db.get(key)
        if data:
            return [data]
        else:
            return ['NO DATA']

    elif command == "transfer_part":
        # During transfer the storage should be unaccessible
        try:
            _available = False
            other_node_ip = form.getfirst("other_node_ip", "")
            other_node_port = form.getfirst("other_node_port", "")
            from_key_id = form.getfirst("from_key_id","")
            to_key_id = form.getfirst("to_key_id","")
            print "Performing partial transfer to: ", other_node_port, "between these ranges: ", from_key_id, "-", to_key_id
                    
            for key in _local_db.keys():
                if  int(from_key_id) < int(key) and int(key) < int(to_key_id):
                    # Check if this hashed key is within transfer range.
                    print "transfering key: ", key, " to: ", other_node_ip, ":", other_node_port
                    value = _local_db.get(key)
                    url = 'http://%s:%s' % (other_node_ip, other_node_port)
                    values = {'cmd' : 'set',
                              'key' : '%s' % key,
                              'value' : '%s' % value }
                    
                    data = urllib.urlencode(values)
                    req = urllib2.Request(url, data)
                    response = urllib2.urlopen(req)
                    _local_db.delete(key)
            # print "SETTING AVAILABLE AGAIN!"
            _available = True
            return ['OK']
        
        except Exception, e:
            traceback.print_exc(file=sys.stdout)
            return ['FAILURE']

    elif command == "transfer":
        # During transfer this storage should be unaccessible and then
        # removed (never accessible again).
        try:
            _available = False
            other_node_ip = form.getfirst("other_node_ip", "")
            other_node_port = form.getfirst("other_node_port", "")
            print "Performing transfer to: ", other_node_port, "This node will becoma unavailable also"
                    
            for key in _local_db.keys():
                print "transfering key: ", key, " to: ", other_node_ip, ":", other_node_port
                value = _local_db.get(key)
                url = 'http://%s:%s' % (other_node_ip, other_node_port)
                values = {'cmd' : 'set',
                          'key' : '%s' % key,
                          'value' : '%s' % value }
                
                data = urllib.urlencode(values)
                req = urllib2.Request(url, data)
                response = urllib2.urlopen(req)
                
            return ['OK']
        except:
            return ['FAILURE']
        
    else:
        return ['UNKNOWN COMMAND']
   

def _get_args():
    """
    Parse launcher arguments and display help.
    """
    usage = 'usage: %prog [options]'
    desc = "Launches a small WSGI (HTTP) server that provides the means of storage to Berkeley DB"

    parser = OptionParser(usage = usage, description = desc)
    parser.add_option('-p',
                      dest='port',
                      type='int',
                      default=8000,
                      help=("Port number to run the server on"))

    (options, args) = parser.parse_args()
    return options
    
def main():
    """
    Main launcher for the WSGI (HTTP) application which provides the
    means of storage to a simple Berkeley DB.

    Only one argument is available (the port number)

    BTREE is choosen to gain performance but as many programmers
    know this is never a obvious choice. Especially when the data
    grows and b-trees become more cumbersome to handle then HASH.
    
    But the layer used to find where to put the data scales in
    specific mannor this will still be enough
    """
    global _local_db

    options = _get_args()
        
    httpd = make_server('', options.port, storage_app)
    
    db_name = "/tmp/distributed_storage_%s.db" % options.port
    _local_db = db.DB()
    _local_db.open(db_name, None, db.DB_BTREE, db.DB_CREATE)
    
    print "Serving storage (HTTP) on port %s..." % options.port

    # Respond to requests until process is killed
    httpd.serve_forever()

if __name__ == "__main__":
    main()
