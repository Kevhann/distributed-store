import time
import rpyc
import json
# import redis

from threading import Thread

def connect_to_server(server):
    [host, port] = server.split(":")
    return rpyc.connect(host, port, config={"allow_all_attrs": True})

# checking if given server is available
def this_server_is_alive(server):
    print('connecting to server {}'.format(server))
    try:
        conn = connect_to_server(server)
        conn.close()
        return True
    except ConnectionRefusedError:
        return False

class NameServerService(rpyc.Service):

    server_list = []

    def __init__(self):
        self.refresh_storage_server_list()
        print('Name server started...')
        thread = Thread(target=self.check_aliveness, args=(0,), daemon=True)
        thread.start()

    def on_connect(self, conn):
        sock = conn._channel.stream.sock
        print('New connection:', sock.getpeername())

    def on_disconnect(self, conn):
        sock = conn._channel.stream.sock
        print('Connection terminated:', sock.getpeername())


    def exposed_health(self):
        return True
    
    def refresh_storage_server_list(self):
        # Load Storage Server Blocks Map
        with open('server_list.json', 'r') as input_file:
            self.server_list = json.load(input_file)
        print('Server addresses reset.')

    def exposed_get_alive_servers(self, max_needed=-1):
        out = []
        i = 0
        for name in self.server_list:
            out.append(name)
            i += 1
            if max_needed > 0 and i == max_needed:
                return out
        return out
    
    # mark server alive
    def check_aliveness(self, check_count):
        # check aliveness & take actions
        check_count += 1
        print('Checking aliveness of storage servers...({})'.format(check_count))

        for server in self.server_list:
            if this_server_is_alive(server):
                print('Server {} is "alive".'.format(server))
            else:
                print('Server {} is "dead".'.format(server))

        # sleep for this time
        time.sleep(10)
        # repeat the process again
        self.check_aliveness(check_count)

    def exposed_insert(self, key, value):
        servers = self.exposed_get_alive_servers()
        print(servers)

        for server in servers:
            try:
                conn = connect_to_server(server)
                conn.root.insert(key, value)
                print('Insert "{}":"{}" into {}'.format(key, value, server))
            except ConnectionRefusedError:
                print('Error while inserting "{}":"{}" into {}'.format(
                    key, value, server))

    def exposed_get(self, key):
        servers = self.exposed_get_alive_servers()

        for server in servers:
            try:
                conn = connect_to_server(server)
                value = conn.root.get(key)
                print('Get "{}":"{}" from {}'.format(key,value, server))
                return value
            except ConnectionRefusedError:
                print('Error while getting key {} from "{}"'.format(
                    key, server))

    def exposed_delete(self, key):
        servers = self.exposed_get_alive_servers()
        for server in servers:
            try:
                conn = connect_to_server(server)
                conn.root.delete(key)
                print('Delete "{}" from {}'.format(key, server))
            except ConnectionRefusedError:
                print('Error while deleting {} from "{}"'.format(
                    key, server))

if __name__ == "__main__":
    from rpyc.utils.server import ThreadedServer
    port = 18860
    t = ThreadedServer(NameServerService(), port=port,
                       protocol_config={"allow_all_attrs": True})
    print('Server details ({}, {})'.format(t.host, port))
    t.start()
