import rpyc
import redis
import time

store = redis.Redis(host='redis', port=6379)

def insert(key, value):
    retries = 5
    while True:
        try:
            return store.set(key, value)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


def getter(key):
    retries = 5
    while True:
        try:
            return store.get(key)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


def delete(key):
    retries = 5
    while True:
        try:
            return store.delete(key)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


class StorageServerService(rpyc.Service):

    def __init__(self):
        pass

    def on_connect(self, conn):
        sock = conn._channel.stream.sock
        print('New connection:', sock.getpeername())

    def on_disconnect(self, conn):
        sock = conn._channel.stream.sock
        print('Connection terminated:', sock.getpeername())

    def exposed_insert(self, key, value):
        insert(key, value)
        print('Put value "{}" to key {}.'.format(value, key))

    def exposed_get(self, key):
        print('wanna get stuff from {}'.format(key))
        value = getter(key)
        print('got stuff from {}'.format(key))

        if (value is None):
            return print('Key not in store')
        print('fetched value {} for key {}'.format(value, key))
        return value



def main(port):
    from rpyc.utils.server import ThreadedServer
    t = ThreadedServer(StorageServerService(), port=port,
                       protocol_config={"allow_all_attrs": True})
    print('Launched server: ({}, {})'.format(t.host, port))
    t.start()


if __name__ == "__main__":
    # args = sys.argv[1:]
    # if len(args)>1:
    #   print('Pass only one argument for port number')
    #   sys.exit(0)
    # elif len(args)==0:
    port = 18861
    # else:
    #   port = int(args[0])
    #   print("port from args: ", port)
    main(port)
