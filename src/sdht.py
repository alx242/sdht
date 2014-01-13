#! /usr/bin/python
# -*- mode: python -*-

"""
The Simplified distributable hash table.

This implementation should be improved to include the proper finger
table and such in due time. But for a simple proof of concept and
distributable storage where data is keept intact it works at the
moment. Probably needs improvements in the backend and frontend. Most
things are keept as KISS (tm) as possible :)

The main function includes a smaller test that can be run. No
unit-tests where included at this time (will appear soon).

"""

import sha, random, pickle
import urllib, urllib2

# The maximum hash value is 2**MAXIMUM_BIT
MAXIMUM_BIT = 160

class NodeError(Exception):
    """
    Our own little exception that tells us if a Node is ok or not.
    """
    pass

class Node():
    """
    The class representation of a node in the sdht.
    """
    
    def __init__(self, ip, port):
        """
        Set the normal value of this Node and also hash out the key_id

        @param ip: IP number of the node
        @type ip: str

        @param port: port number of the node
        @type port: str
        """
        self.next = None
        self.ip = ip
        self.port = port
        self.key_id = long(sha.new("%s:%s" % (ip, port)).hexdigest(), 16)

    def transfer(self, other_node):
        """
        Transfer all hashed keys from this node to another one

        @param other_node: Other node that this node should transfer
        its content to
        @type other_node: Node

        @return: If the transfer was ok we return True or False if not
        @rtype: bool
        """
        url = 'http://%s:%s' % (self.ip, self.port)
        values = {'cmd' : 'transfer',
                  'other_node_ip': other_node.ip,
                  'other_node_port': other_node.port}
        
        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        
        result = response.read()
        return result and result != 'NO DATA'

    def steal_range(self, other_node, from_id, to_id):
        """
        Steal all hashed keys from another node to this node
        (depending on their key_id).
        
        The node steals from other_node but the data passed is
        actually to the node that is being stolen from to send its
        data to this node. Confused?

        @param other_node: Other node that this node should transfer
        its content to
        @type other_node: Node

        @param from_id: starting hash-id to transfer
        @type from_id: long

        @param to_id: ending hash-id to transfer
        @type to_id: long

        @return: If the transfer was ok we return True or False if not
        @rtype: bool
        """
        url = 'http://%s:%s' % (other_node.ip, other_node.port)
        values = {'cmd' : 'transfer_part',
                  'from_key_id': from_id,
                  'to_key_id': to_id,
                  'other_node_ip': self.ip,
                  'other_node_port': self.port}
        
        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        
        result = response.read()
        return result and result != 'NO DATA'

    def check(self):
        """
        Check if a node is ok and up and running

        @return: If the node responded ok we return True otherwise False
        @rtype: bool
        """
        url = 'http://%s:%s' % (self.ip, self.port)
        values = {'cmd' : 'check'}
        
        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        
        result = response.read()
        return result and result == 'OK'
    
    def __setitem__(self, key, value):
        """
        Set an item in the storage
        
        @param key: Hashed key to set
        @type key: long

        @param key: Hashed key to set
        @type key: long

        @param key: Serialized data to set
        @type key: str
        """
        url = 'http://%s:%s' % (self.ip, self.port)
        values = {'cmd' : 'set',
                  'key' : '%s' % key,
                  'value' : '%s' % value }

        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        
        if response.read() != "OK":
            raise ValueError ("Could not set value in storage")

    def __getitem__(self, key):
        """
        Get an item from the storage

        @param key: Hashed key to set
        @type key: long
        """
        url = 'http://%s:%s' % (self.ip, self.port)
        values = {'cmd' : 'get',
                  'key' : '%s' % key }

        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        result = response.read()
        if result and result != 'NO DATA':
            return result
        
        elif not result:
            raise NodeError("Node isn't responding (has it gone down?)")
        else:
            raise KeyError(key)

    def __repr__(self):
        """
        Makes it simple to print out a Node.
        """
        return "<Node '%s', port '%s'>" % (self.key_id, self.port)

# This is a clockwise ring distance function.
#
def distance(a, b):
    """
    Lets determine the distance between two hashes.

    If the same hash value the result is 0

    If a has a hash value less then b then return b - a (a positive value)

    Else get the current maximum-hash and add it to b - a (we have
    passed by the last element and we want to get the distance above
    it).
    
    @param a: A hashed value to compare
    @type a: long

    @param b: A hashed value to compare
    @type b: long

    @return: The probable distance between current nodes or the current nodes distance + the maximum hash
    @rtype: long
    
    """
    if a == b:
        return 0
    elif a < b:
        return b - a
    else:
        # If the next key has a id higher then the current hash. This
        # distance has to be higher then previous unless it is the
        # only node. Here the distance is maximum hash + the distance
        # between the next nodes
        #
        return _node_list[len(_node_list)-1].key_id + (b - a)

    # This is more correct version where the maximum
    # return (2**MAXIMUM_BIT) + (b-a) # This is the proper DHT way


def find_node(start, key):
    """
    From the start node, find the node responsible for the target key

    We will keep wandering the nodes until we find a suitable sport
    for our hashed key to be stored.

    If there is _node_list with more then one element and the distance
    between current node and key is bigger then the distance between
    the next-node and key go to the next node
    
    @param start: A starting node that we check if it is the correct
    node for this hashed key
    @type start: Node

    @param key: A hashed key that we want to find the correct node for
    @type key: long

    @return the node for where this key belongs to
    @rtype: Node
    """
    current = start
    
    while len(_node_list) > 1 and distance(current.key_id, key) > distance(current.next.key_id, key):
        current = current.next
    return current

def _lookup(start, key):
    """
    Find the responsible node and get the value for the key

    @param start: A starting node that we check if it is the correct
    node for this hashed key
    @type start: Node

    @param key: A hashed key that we want to get the value for
    @type key: long

    @return: The value in a node
    @return: str
    """
    node = find_node(start, key)
    return node[key]

def _store(start, key, value):
    """
    Find the responsible node and store the value with the key

    @param start: A starting node that we check if it is the correct
    node for this hashed key
    @type start: Node

    @param key: A hashed key that we want to set the value for
    @type key: long

    @param key: A serialized value we want to set in a storage
    @type key: str

    """
    node = find_node(start, key)
    node[key] = value


# Instead of using a previous pointer a _node_list is used to assisst
# for this purpose. Useally these shouldn't mixed up but the next
# pointer simplifies the lookup algorithm while the _node_list assists
# with the joining and removing of nodes. Maybe this should be
# re-written for clarity, but I didn't have any trouble reading the
# code still.
#
_node_list = []

def remove (node):
    """
    Remove a node from the ring.

    Please note that is a more official version of de-registration of
    a node which makes sure that now values is lost from the ring by
    transfering any removed data to other nodes when one node is
    removed (unless it is the last node that is).

    @param start: A node we want to remove from the ring
    @type start: Node
    """
    if len(_node_list) > 2:
        index = _node_list.index(node)
        if index > 0:
            # Not first element
            _node_list[index-1].next = node.next
            # Transfer data to previous node
            node.transfer(_node_list[index-1])
        else:
            # Is first element
            _node_list[len(_node_list)-1].next = node.next
            # Transfer data to new first node
            node.transfer(node.next)
        _node_list.remove(node)
        
    elif len(_node_list) == 2:
        _node_list.remove(node)
        _node_list[0].next = None
        node.transfer(_node_list[0])
        
    else:
        _node_list.remove(node)
        # No where transfer the data.
        
def join(node):
    """
    Add a node to the node-ring.
    
    Useally nodes are added at the start but if a node is added at a
    latter state hashes keys and values might need to be moved around
    a bit. See the following example for how this works.
    
    Example of how hashes get stolen:
    
    How the recalculations are done.
    node 1 > 2 3 4 5 6 7
    node 8 > 8 9 10
    
    Get all values from node 1 that are useful to new node 4 and remove them from node 1
    
    node 1 > 2 3 
    node 4 > 4 5 6 7
    node 8 > 8 9 10
    
    @param start: A node we want to add to the ring
    @type start: Node

    """
    if not node.check():
        raise NodeError ("Node '%s' isn't responding" % node)

    if len(_node_list) == 0:
        # Insert first
        _node_list.append(node)
        
    elif len(_node_list) == 1:
        first = _node_list[0]
        if node.key_id < first.key_id:
            # Insert first
            _node_list.insert(0, node)
            first.next = node
            node.next = first
            # Steal hash:es from the "last" node to the new first node
            node.steal_range(first, node.key_id, first.key_id)
        else:
            # Insert last
            _node_list.append(node)
            node.next = first
            first.next = node
            # Steal hash:es from the previous node to the new node (to
            # the maximum amount)
            node.steal_range(first, first.key_id, 2**MAXIMUM_BIT)
            
    else:
        current_index = 0
        for current_node in _node_list:
            if node.key_id < current_node.key_id:
                node.next = current_node
                if current_index == 0:
                    # We are inserting the node as the new first
                    # element in the list

                    # Point the last node in the finger list to the
                    # node being inserted
                    _node_list[len(_node_list)-1].next = node
                    
                    # Steal hash:es in the first node to the new first
                    # node
                    node.steal_range(_node_list[len(_node_list)-1], node.key_id, _node_list[0].key_id)
                else:
                    # We are inserting the node at a regular interval
                    # in the list

                    # Point latest node to current node being inserted
                    _node_list[current_index-1].next = node
                    
                    # Steal hash:es from the previous node to the new
                    # node (to the maximum amount)
                    node.steal_range(_node_list[current_index-1], node.key_id, 2**MAXIMUM_BIT)
                    
                _node_list.insert(current_index, node)
                break
            
            current_index += 1

        if current_index == len(_node_list):
            # Insert the as the last node in the list
            _node_list[current_index-1].next = node
            _node_list.append(node)
            node.next = _node_list[0]
            
            # Steal hash:es in the previous last node to the new last
            # node.
            node.steal_range(_node_list[current_index-1], node.key_id, 2**MAXIMUM_BIT)
            
def set(key, value):
    """
    Set a value in the storage

    @param key: The key for a value we want to store in a storage
    @type key: str

    @param value: The value connected to the key we also want to store
    in the storage
    @type value: object
    """
    hashed_key = long(sha.new(key).hexdigest(), 16)
    serialized_value = pickle.dumps(value) # Use default protocol
    _store(_node_list[0], hashed_key, serialized_value)
    
def get(key):
    """
    Get a value from the storage

    @param key: The key for a value we want get from a storage
    @type key: str

    @return: The value stored for this key
    @rtype: object

    """
    hashed_key = long(sha.new(key).hexdigest(), 16)
    serialized_value = _lookup(_node_list[0], hashed_key)
    return pickle.loads(serialized_value)

def main():
    """
    Runs a simple example on the node-ring. Requires that 4 nodes
    have been launched on the local machine on the ports 8000-8003.

    This example can be totally ignored.
    """
    print "Creating four test nodes to run tests on (get and set values)"
    
    node_one = Node('127.0.0.1', '8000') 
    node_two = Node('127.0.0.1', '8001')
    node_three = Node('127.0.0.1', '8002')
    node_four = Node('127.0.0.1', '8003')

    if not node_one.check() or not node_two.check() or not node_three.check() or not node_four.check():
        print ("Premissions haven't been set for this test to be run. Make sure all "
               "four nodes on the local machine is up and running on the ports "
               "8000-8003. ")
        return

    join(node_three)
    join(node_one)
    join(node_two)
    join(node_four)
    
    # Store the key
    key_a = "a"
    key_b = "b"
    key_c = "c"
    value_a = "a test value: a"
    value_b = "a test value: b"
    value_c = "a test value: c"
    
    set(key_a, value_a)
    set(key_b, value_b)
    set(key_c, value_c)
    
    # Wanna try and remove some node? Add any of these functions to see if it works.
    # remove(node_one)
    # remove(node_two)
    # remove(node_three)
    # remove(node_four)
    
    # Test the keys
    print "Found value for key_a in the ring:", get(key_a) == value_a 
    print "Found value for key_b in the ring:", get(key_b) == value_b
    print "Found value for key_b in the ring:", get(key_c) == value_c

if __name__ == "__main__":
    main()


