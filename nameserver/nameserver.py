import time
import rpyc

import sys

# import redis

from threading import Thread

STORE_VERSION = 0
SERVER_TIMEOUT_S = 5


def connect_to_server(server):
    print("connecting to {}".format(server))
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

    # server_list is a dict with server host:port as key,
    # and [version, aliveness] as value
    server_list = {}

    # The version of the store, i.e. the
    # most recent version of any connected nameservers
    store_version = 0

    def __init__(self):
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

    def exposed_update_store_to_latest(self):
        return True

    def get_storageserver_version(self, server):
        return self.server_list[server][0]

    def get_storageserver_alive_info(self, server):
        return self.server_list[server][1]

    def set_storageserver_version(self, server, data):
        self.server_list[server][0] = data

    def set_storageserver_alive_info(self, server, data):
        self.server_list[server][1] = data

    def incr_storageserver_alive_info(self, server):
        self.server_list[server][1] += 1

    def update_server(self, server, version_from, peers):
        print(
            "Updating server {} from version {} to {} using peers {}".format(
                server, version_from, STORE_VERSION, peers
            )
        )
        conn = connect_to_server(server)
        conn.root.update_store(version_from, STORE_VERSION, peers)

    def exposed_storage_enlist(self, server, version):
        if server not in self.server_list:
            print("Storage server {} with version {} joined!".format(server, version))
        self.server_list[server] = [version, 0]

        # If connected store is not up-to-date, update it
        if version < STORE_VERSION:
            self.update_single_server(server, version)

    def update_single_server(self, server, version):
        global STORE_VERSION
        latest = []
        for server in self.server_list:
            if self.get_storageserver_version(server) == STORE_VERSION:
                latest.append(server)

        self.update_server(server, version, latest)

    def get_alive_servers(self):
        global STORE_VERSION
        latest = []
        outdated = []
        for server in self.server_list:
            if self.get_storageserver_version(server) == STORE_VERSION:
                latest.append(server)
            else:
                outdated.append(server)

        # If no store with latest version, then roll back to latest active version and start again from there
        if len(latest) == 0:
            rollback = max(
                (
                    self.get_storageserver_version(server)
                    for server in list(self.server_list)
                )
            )
            print(
                (
                    "No stores with latest version\n"
                    "Rolling back from version {} to {}".format(STORE_VERSION, rollback)
                )
            )
            STORE_VERSION = rollback
            self.get_alive_servers()

        for server in outdated:
            version = self.get_storageserver_version(server)
            self.update_server(server, version, latest)

        return latest

    # check is servers are alive
    def check_aliveness(self, count):
        count += 1
        for server in list(self.server_list):
            if self.get_storageserver_alive_info(server) > SERVER_TIMEOUT_S:
                # Remove dead server
                self.server_list.pop(server)
                print("Server {} has died.".format(server))
            else:
                # Update server aliveness
                self.incr_storageserver_alive_info(server)

        print("Known storageservers: {}".format(self.server_list))
        # sleep for this time
        time.sleep(1)
        # repeat the process again
        self.check_aliveness(count)

    def exposed_insert(self, key, value):
        global STORE_VERSION
        servers = self.get_alive_servers()
        print(servers)

        for server in servers:
            try:
                conn = connect_to_server(server)
                ver = conn.root.insert(key, value)
                STORE_VERSION = ver

                print('Insert "{}":"{}" into {}'.format(key, value, server))
            except ConnectionRefusedError:
                print(
                    'Error while inserting "{}":"{}" into {}'.format(key, value, server)
                )

        return True

    def exposed_get(self, key):
        servers = self.get_alive_servers()

        for server in servers:
            try:
                conn = connect_to_server(server)
                value = conn.root.get(key)
                print('Get "{}":"{}" from {}'.format(key, value, server))
                return value
            except ConnectionRefusedError:
                print('Error while getting key {} from "{}"'.format(key, server))

    def exposed_get_store_dumps(self):
        servers = self.get_alive_servers()

        dump = {}

        for server in servers:
            try:
                conn = connect_to_server(server)
                value = conn.root.dump_keys()
                print("Get dump from {}".format(server))
                dump[server] = value
            except ConnectionRefusedError:
                print('Error while getting dump from "{}"'.format(server))
        return dump

    def exposed_delete(self, key):
        servers = self.get_alive_servers()
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
        print("Missing nameserver info in args")
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
