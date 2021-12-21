import rpyc
import redis
import time
import sys
from threading import Thread


CONN = None
STORE = None

NAMESERVER_IP = None
NAMESERVER_PORT = None
REDIS_PORT = None
REDIS_HOST = None
STORAGESERVER = None

VER_KEY = "__VERSION_KEY__"
LOG_KEY = "__LOG_KEY__"
STORE_VERSION = 0


def dump_store_keys():
    return STORE.keys()


def log_store_action(operation):
    global STORE_VERSION
    STORE.lpush(LOG_KEY, operation)
    STORE_VERSION = STORE.incr(VER_KEY)
    return STORE_VERSION


def get_version_number():
    version = STORE.get(VER_KEY)
    if version is None:
        return 0
    return version


def set_version_number():
    global STORE_VERSION
    STORE_VERSION = get_version_number()


def get_operations(offset=0):
    result = STORE.lrange(LOG_KEY, offset, -1)
    return result


def apply_operations(ops):
    for operation in ops:
        print(operation)
        operation = operation.decode("ascii")
        op = operation.split(" ")

        if op[0] == "insert":
            insert(op[1], op[2])


def insert(key, value):
    STORE.set(key, value)
    return log_store_action("insert {} {}".format(key, value))


def getter(key):
    result = STORE.get(key).decode("ascii")
    return result


def delete(key):
    STORE.delete(key)
    return log_store_action("delete {}".format(key))


def connect_to_nameserver(count_retry=1, max_retry=3):
    global CONN
    print("Connecting to nameserver at {}:{}".format(NAMESERVER_IP, NAMESERVER_PORT))
    try:
        CONN = rpyc.connect(
            NAMESERVER_IP, NAMESERVER_PORT, config={"allow_all_attrs": True}
        )
    except ConnectionError:
        CONN = None

    time.sleep(1)

    if CONN is None:
        print("Connection couldn't be established.\n")
        time.sleep(1)
        if count_retry <= max_retry:
            print("Attempt {} out of {}".format(count_retry, max_retry))
            return connect_to_nameserver(count_retry + 1, max_retry)
        else:
            print("Maximum allowed attempts made. Closing the application now!\n")
            return False
    else:
        print("Connected!")
        time.sleep(1)
        return True


def connect_to_peer(server, count_retry=1, max_retry=3):
    [peer_ip, peer_port] = server.split(":")
    print("Connecting to peer at {}:{}".format(peer_ip, peer_port))
    try:
        return rpyc.connect(peer_ip, peer_port, config={"allow_all_attrs": True})
    except ConnectionError:
        pass

    print("Connection couldn't be established.\n")
    time.sleep(1)
    if count_retry <= max_retry:
        print("Attempt {} out of {}".format(count_retry, max_retry))
        return connect_to_peer(server, count_retry + 1, max_retry)
    else:
        print("Maximum allowed attempts made. Closing the application now!\n")
        return False


class StorageServerService(rpyc.Service):
    def __init__(self):
        connect_to_nameserver()
        thread = Thread(target=self.poll_nameserver, args=(0,), daemon=True)
        thread.start()
        set_version_number()

    def on_connect(self, conn):
        sock = conn._channel.stream.sock
        print("New connection:", sock.getpeername())

    def on_disconnect(self, conn):
        sock = conn._channel.stream.sock
        print("Connection terminated:", sock.getpeername())

    # poll nameserver to keep the connection alive
    def poll_nameserver(self, count):
        count += 1
        CONN.root.storage_enlist(STORAGESERVER, STORE_VERSION)
        # sleep for this time
        time.sleep(1)
        # repeat the process again
        self.poll_nameserver(count)

    def exposed_update_store(self, version_from, version_to, peers):
        print(
            "Updating self from version {} to {} using peers {}".format(
                version_from, version_to, peers
            )
        )

        conn = connect_to_peer(peers[0])
        ops = conn.root.get_store_log(version_from, version_to)
        print("Applying {} operations".format(len(ops)))
        apply_operations(ops)

    def exposed_get_store_log(self, version_from, version_to):
        if version_to != STORE_VERSION:
            print(
                "Version mismatch! Asked for version {}, current store version is {}".format(
                    version_to, STORE_VERSION
                )
            )
            return []
        return get_operations(version_from)

    def exposed_insert(self, key, value):
        result = insert(key, value)
        print('Put value "{}" to key {}.'.format(value, key))
        return result

    def exposed_get(self, key):
        value = getter(key)
        if value is None:
            return print("Key not in store")
        print("fetched value {} for key {}".format(value, key))
        return value

    def exposed_dump_keys(self):
        print("Dumping all keys in store")
        return dump_store_keys()


def main():
    global NAMESERVER_IP, NAMESERVER_PORT, STORAGESERVER, REDIS_PORT, REDIS_HOST, STORE

    args = sys.argv
    print(args)
    if len(args) < 4:
        print(
            (
                "Missing args!\n"
                "The program requires the following arguments:\n"
                "Location of this server as 'host:port'\n"
                "Location of the nameserver as 'host:port'\n"
                "Location of the redis instance as 'host:port'\n"
            )
        )
        return 0
    STORAGESERVER = args[1]
    [nameserver_host, nameserver_port] = args[2].split(":")

    NAMESERVER_IP = nameserver_host
    NAMESERVER_PORT = nameserver_port

    [redis_host, redis_port] = args[3].split(":")

    REDIS_HOST = redis_host
    REDIS_PORT = int(redis_port)

    STORE = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

    from rpyc.utils.server import ThreadedServer

    storageserver_port = STORAGESERVER.split(":")[1]
    t = ThreadedServer(
        StorageServerService(),
        port=storageserver_port,
        protocol_config={"allow_all_attrs": True},
    )
    print("Launched server: ({}, {})".format(t.host, storageserver_port))
    t.start()


if __name__ == "__main__":
    main()
