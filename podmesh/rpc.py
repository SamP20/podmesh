import json
from collections.abc import Generator
from socket import socket
from threading import Thread

import cattrs

MAX_BUFSIZE = 4096


class SocketDelimiter(object):
    def __init__(self, socket: socket, **kwargs):
        self.socket = socket
        super().__init__(**kwargs)

    def socket_iter(self) -> Generator[bytes, None, None]:
        buffer = bytearray(MAX_BUFSIZE)
        mview = memoryview(buffer)
        write_idx = 0

        while True:
            try:
                numbytes = self.socket.recv_into(mview[write_idx:], len(buffer)-write_idx)
            except TimeoutError:
                continue
            if numbytes == 0:
                break
            if numbytes + write_idx >= len(buffer):
                raise RuntimeError("Recieve buffer overflowed")
            newline_idx = buffer.find(b'\n', write_idx, write_idx+numbytes)
            write_idx += numbytes
            while newline_idx >= 0:
                yield buffer[0:newline_idx]
                newline_idx += 1 # Skip the newline
                excess_bytes = write_idx-newline_idx
                buffer[0:excess_bytes] = buffer[newline_idx:write_idx]
                write_idx = excess_bytes
                newline_idx = buffer.find(b'\n', 0, write_idx)


class RpcConnection(SocketDelimiter):
    def __init__(self, socket, **kwargs):
        self.methods = {}
        super().__init__(socket, **kwargs)

    def register_method(self, method, dtype, handler):
        self.methods[method] = (dtype, handler)

    def send(self, method, data):
        dtype = self.methods[method][0]
        if not isinstance(data, dtype):
            raise RuntimeError(f"Data is wrong type for method {method}. Expected {dtype}, got {type(data)}")
        payload = cattrs.unstructure(data)

        msg = {
            "method": method,
            "payload": payload
        }
        raw = json.dumps(msg).encode() + b'\n'
        self.socket.sendall(raw)

    def runserver(self):
        def run_thread():
            for buf in self.socket_iter():
                self.handle_message(buf)
        self.server_thread = Thread(target=run_thread)
        self.server_thread.daemon = True
        self.server_thread.start()

    def handle_message(self, buf: bytes):
        msg = json.loads(buf)
        try:
            method = msg["method"]
            payload = msg["payload"]
            dtype = self.methods[method][0]
            handler = self.methods[method][1]
            data = cattrs.structure(payload, dtype)
            handler(self, data)
        except Exception as ex:
            print(ex)
