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


def insert(key, value):
    retries = 5
    while True:
        try:
            return STORE.set(key, value)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


def getter(key):
    retries = 5
    while True:
        try:
            return STORE.get(key).decode("ascii")
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


def delete(key):
    retries = 5
    while True:
        try:
            return STORE.delete(key)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


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


class StorageServerService(rpyc.Service):
    def __init__(self):
        connect_to_nameserver()
        thread = Thread(target=self.poll_nameserver, args=(0,), daemon=True)
        thread.start()

    def on_connect(self, conn):
        sock = conn._channel.stream.sock
        print("New connection:", sock.getpeername())

    def on_disconnect(self, conn):
        sock = conn._channel.stream.sock
        print("Connection terminated:", sock.getpeername())

    # poll nameserver to keep the connection alive
    def poll_nameserver(self, count):
        count += 1
        CONN.root.storage_enlist(STORAGESERVER)

        # sleep for this time
        time.sleep(1)
        # repeat the process again
        self.poll_nameserver(count)

    def exposed_insert(self, key, value):
        insert(key, value)
        print('Put value "{}" to key {}.'.format(value, key))

    def exposed_get(self, key):
        print("wanna get stuff from {}".format(key))
        value = getter(key)
        print("got stuff from {}".format(key))

        if value is None:
            return print("Key not in store")
        print("fetched value {} for key {}".format(value, key))
        return value


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
