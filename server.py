import zmq
import shelve
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

# HTTP #

httpd = None

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        channel_name = self.path[1:]

        content_length = int(self.headers['Content-Length'])
        if content_length > 1024:
            self.send_error(413)
            return

        data = self.rfile.read(content_length)

        channel_send(channel_name, data)
        self.send_response(200)
        self.end_headers()
        self.request.sendall(b'OK')

def http_setup():
    global httpd

    bind_address = ('0.0.0.0', 20451)

    httpd = HTTPServer(bind_address, Handler)
    httpd.timeout = 0

def http_loop():
    httpd.handle_request()

# ZMQ #

zmq_socket = None

def zmq_setup():
    global zmq_socket
    context = zmq.Context()
    zmq_socket = context.socket(zmq.XPUB)
    zmq_socket.setsockopt(zmq.XPUB_VERBOSE, 1)
    zmq_socket.bind('tcp://*:20452')

def zmq_send(channel, msg):
    zmq_socket.send_multipart((channel, msg))

# DB #

store = None

def db_setup():
    global store
    store = shelve.open('db.shelve')

def db_store(channel, value):
    store[channel] = value

def db_get(channel):
    try:
        return store[channel]
    except KeyError:
        return None

# MAIN #

def main():
    http_setup()
    zmq_setup()
    db_setup()

    run_loop()

def run_loop():
    while True:
        http_loop()

        rlist, _, _ = zmq.select([httpd, zmq_socket], [], [])

        if zmq_socket in rlist:
            new_subscriber()

def new_subscriber():
    event = zmq_socket.recv()
    # Event is one byte 0=unsub or 1=sub, followed by topic
    if event[0] == b'\x01':
        topic = event[1:]
        cached_value = db_get(topic)
        if cached_value is not None:
            print ("Sending cached topic %s" % topic)
            zmq_socket.send_multipart([topic, cached_value])

def channel_send(channel, msg):
    db_store(channel, msg)
    zmq_send(channel, msg)

if __name__ == '__main__':
    main()

