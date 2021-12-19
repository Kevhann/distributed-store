from cmd import Cmd
import time
import math
import sys

from prompt_toolkit import print_formatted_text as print, HTML
from prompt_toolkit.styles import Style
import rpyc

# TODO: fins some nicer colours
style = Style.from_dict(
    {
        "red": "#8f0313",
        "green": "#24a30d",
        "blue": "#1129ad",
        "orange": "#de720d",
        "b": "bold",
        "i": "italic",
    }
)


CONN = None
NAMESERVER_IP = None
NAMESERVER_PORT = None


def connect_to_ns(count_retry=1, max_retry=3):
    global CONN
    print(
        HTML(
            "<orange>Connecting to nameserver at {}:{}</orange>".format(
                NAMESERVER_IP, NAMESERVER_PORT
            )
        )
    )
    try:
        CONN = rpyc.connect(
            NAMESERVER_IP, NAMESERVER_PORT, config={"allow_all_attrs": True}
        )
    except ConnectionError:
        CONN = None

    time.sleep(1)

    if CONN is None:
        print(HTML("<red>Connection couldn't be established.\n</red>"))
        time.sleep(1)
        if count_retry <= max_retry:
            print("Attempt {} out of {}".format(count_retry, max_retry))
            return connect_to_ns(count_retry + 1, max_retry)
        else:
            print("Maximum allowed attempts made. Closing the application now!\n")
            return False
    else:
        print(HTML("<green>Connected!</green>"))
        time.sleep(1)
        return True


def nameserver_is_responding():
    global CONN
    try:
        return CONN.root.health()
    except EOFError:
        CONN = None
        print(HTML("<red>Error</red>: Connection to nameserver lost!"))
        print(HTML("<green>Retrying</green> in 5 seconds..."))
        time.sleep(5)

        return True if connect_to_ns() else False


def insert_in_store(key, value):
    if nameserver_is_responding():
        try:
            return CONN.root.insert(key, value)
        except ConnectionRefusedError:
            print(
                "Connection refused by nameserver while trying to put key {}".format(
                    key
                )
            )
    return False


def get_from_store(key):
    if nameserver_is_responding():
        try:
            return CONN.root.get(key)
        except ConnectionRefusedError:
            print(
                "Connection refused by nameserver while trying to get value of key {}".format(
                    key
                )
            )


class MainPrompt(Cmd):
    prompt = "[? or 'help'] >> "
    intro = (
        "> Welcome to distributed store.\n"
        "> The store is a key-value store, with only ascii strings supperted for now\n"
        "> Type '?' or 'help' to see available commands.\n"
    )

    def preloop(self):
        print(HTML("\n------------- <green>Session Started</green> -------------\n"))

    # TODO Parse args better
    def parse_args(self, cmd_name, args, min_required=0, max_required=float("inf")):
        args = args.strip()
        args = args.split(" ") if len(args) > 0 else args
        N = len(args)

        if N < min_required or N > max_required:
            if min_required == max_required:
                required = min_required
            else:
                required = "{} ".format(min_required)
                if math.isinf(max_required):
                    required += "or more"
                else:
                    required += "to {}".format(max_required)

            print(
                HTML(
                    "<red>Error</red>: <b>{}</b> expected <orange>{}</orange> args, got <orange>{}</orange>.".format(
                        cmd_name, required, N
                    )
                )
            )
            print(
                HTML(
                    "<green><b>TIP</b></green>: Try <b>help {}</b> for correct usage.\n".format(
                        cmd_name
                    )
                )
            )
            return None
        return args

    def print_help(self, form, result):
        form = form.split(" ")
        form[0] = "<orange>{}</orange>".format(form[0])
        form = " ".join(form)
        print(HTML("Usage Format: {} \nResult: {}\n".format(form, result)))

    def print_response(self, response):
        output = (
            "<green>Success</green>:"
            if response["status"] == 1
            else "<red>Failed</red>:"
        )
        output += " {}".format(response["message"])
        print(HTML(output))

    def do_quit(self, arg):
        print(HTML("\n-------------- <red>Session Ended</red> -------------- \n"))
        return True

    def help_quit(self):
        self.print_help("[exit] [x] [q] [Ctrl-D]", "<red>Quit</red> the application.")

    def do_insert(self, args):
        [key, value] = self.parse_args("insert", args, 2, 2)
        success = insert_in_store(key, value)
        if success:
            print(
                HTML(
                    "<green>Value {} inserted to {} successfully</green>".format(
                        value, key
                    )
                )
            )
        else:
            print(HTML("<red>Error while inserting value to store</red>"))

    def help_insert(self):
        self.print_help("insert [key] [value]", "Insert a key-value pair to the store")

    def do_get(self, args):
        # TODO: Fix after arg parsing is done
        [key] = self.parse_args("get", args, 1, 1)
        value = get_from_store(key)
        if value is None:
            print(HTML("<orange>Key {} not found in store</orange>".format(key)))
        else:
            print(HTML('<green>Value "{}" found in store</green>'.format(value)))

    def help_get(self):
        self.print_help("get [key]", "Get a key-value pair from the store")

    def default(self, inp):
        if inp == "x" or inp == "q":
            return self.do_quit(inp)
        else:
            print(
                HTML(
                    "Invalid command! \n > Type <green>help</green> for command list.\n"
                )
            )

    def emptyline(self):
        pass


def main():
    global NAMESERVER_IP
    global NAMESERVER_PORT

    args = sys.argv
    if len(args) < 2:
        print(HTML("<red>Error</red>: Missing nameserver info in args"))
        return 0
    [host, port] = args[1].split(":")

    NAMESERVER_IP = host
    NAMESERVER_PORT = int(port)

    if connect_to_ns():
        MainPrompt().cmdloop()


if __name__ == "__main__":
    main()
