import time
import rpyc

import sys

# import redis

from threading import Thread

SERVER_TIMEOUT_S = 5


def connect_to_server(server):
    [host, port] = server.split(":")
    return rpyc.connect(host, port, config={"allow_all_attrs": True})


# checking if given server is available
def this_server_is_alive(server):
    print("connecting to server {}".format(server))
    try:
        conn = connect_to_server(server)
        conn.close()
        return True
    except ConnectionRefusedError:
        return False


class NameServerService(rpyc.Service):

    server_list = {}

    def __init__(self):
        # self.refresh_storage_server_list()
        print("Name server started...")
        thread = Thread(target=self.check_aliveness, args=(0,), daemon=True)
        thread.start()

    def on_connect(self, conn):
        sock = conn._channel.stream.sock
        print("New connection:", sock.getpeername())

    def on_disconnect(self, conn):
        sock = conn._channel.stream.sock
        print("Connection terminated:", sock.getpeername())

    def exposed_health(self):
        return True

    def exposed_storage_enlist(self, server):
        if server not in self.server_list:
            print("Storage server {} joined!".format(server))
        self.server_list[server] = 0

    def exposed_get_alive_servers(self, max_needed=-1):
        out = []
        i = 0
        for name in self.server_list:
            out.append(name)
            i += 1
            if max_needed > 0 and i == max_needed:
                return out
        return out

    # check is servers are alive
    def check_aliveness(self, count):
        count += 1
        for server in list(self.server_list):
            if self.server_list[server] > SERVER_TIMEOUT_S:
                self.server_list.pop(server)
                print("Server {} has died.".format(server))
            else:
                self.server_list[server] += 1

        # sleep for this time
        time.sleep(1)
        # repeat the process again
        self.check_aliveness(count)

    def exposed_insert(self, key, value):
        servers = self.exposed_get_alive_servers()
        print(servers)

        for server in servers:
            try:
                conn = connect_to_server(server)
                conn.root.insert(key, value)
                print('Insert "{}":"{}" into {}'.format(key, value, server))
            except ConnectionRefusedError:
                print(
                    'Error while inserting "{}":"{}" into {}'.format(key, value, server)
                )
                return False
        return True

    def exposed_get(self, key):
        servers = self.exposed_get_alive_servers()

        for server in servers:
            try:
                conn = connect_to_server(server)
                value = conn.root.get(key)
                print('Get "{}":"{}" from {}'.format(key, value, server))
                return value
            except ConnectionRefusedError:
                print('Error while getting key {} from "{}"'.format(key, server))

    def exposed_delete(self, key):
        servers = self.exposed_get_alive_servers()
        for server in servers:
            try:
                conn = connect_to_server(server)
                conn.root.delete(key)
                print('Delete "{}" from {}'.format(key, server))
            except ConnectionRefusedError:
                print('Error while deleting {} from "{}"'.format(key, server))


def main():

    args = sys.argv
    if len(args) < 2:
        print(HTML("<red>Error</red>: Missing nameserver info in args"))
        return 0
    port = args[1]

    from rpyc.utils.server import ThreadedServer

    t = ThreadedServer(
        NameServerService(), port=port, protocol_config={"allow_all_attrs": True}
    )
    print("Server details ({}, {})".format(t.host, port))
    t.start()


if __name__ == "__main__":
    main()
