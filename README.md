# Introduction

This is a simple python-based implementation of a distributed storage

# How to launch the system?

The easiest way to launch is using docker-compose. In the project directory run

```
docker-compose up
```

To launch all services. Then in another terminal connect to the client with

```
docker attach <client container name>
```

Project can be also run without docker by running the services manually with `python3`. This requires that the following dependencies are installed:

**For client**: Python3 with rpyc, prompt-toolkit, prompt.

**For NameServer**: Python3 with rpyc

**For StorageServers**: Python3 with rpyc and redis

# How to use it?

Once you run the client script and are connected to the nameserver. Simply try these for usage help:

- type `help` and hit enter to see all available commands:

# Architecture

TODO:

# Communication Protocols - RPyC

RPyC is a popular Python library used for remote procedure calls. All communications between Naming Server, Storage Servers, and the Client in our application is done using RPyC as it is simple to use and allows us to call remote methods and attributes in a local context.
