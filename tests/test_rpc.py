import json
import socket
from threading import Thread

import pytest
from attrs import define
from podmesh import RpcConnection
from podmesh.rpc import MAX_BUFSIZE, SocketDelimiter


@define
class ExampleData:
    a: int
    b: str


def test_delimit_single_packet():
    s0, s1 = socket.socketpair()
    sd = SocketDelimiter(s1)

    s0.send(b'abcdefgh\n')
    result = next(sd.socket_iter())
    assert result == b'abcdefgh'

def test_delimit_split_packet():
    s0, s1 = socket.socketpair()
    sd = SocketDelimiter(s1)
    s0.send(b'abc')
    s0.send(b'defgh\n')
    result = next(sd.socket_iter())
    assert result == b'abcdefgh'

def test_delimit_multiple_packes():
    s0, s1 = socket.socketpair()
    sd = SocketDelimiter(s1)

    s0.send(b'abcdefgh\n1234567\n')
    iter = sd.socket_iter()
    assert  next(iter) == b'abcdefgh'
    assert  next(iter) == b'1234567'

def test_packet_too_large():
    s0, s1 = socket.socketpair()
    sd = SocketDelimiter(s1)

    bigbuf = b'a'*MAX_BUFSIZE
    s0.send(bigbuf)
    with pytest.raises(RuntimeError):
        next(sd.socket_iter())

def test_rpc_decode():
    c = RpcConnection(None)
    my_result = None
    def handler(conn, d):
        nonlocal my_result
        my_result = d
    c.register_method("test", ExampleData, handler)
    c.handle_message(b'{"method": "test", "payload": {"a": 9, "b": "world"}}')
    assert my_result.a == 9
    assert my_result.b == "world"

def test_rpc_encode():
    s0, s1 = socket.socketpair()
    c = RpcConnection(s0)
    c.register_method("test", ExampleData, None)
    c.send("test", ExampleData(45, "stuff"))
    buf = s1.recv(1024)
    msg = json.loads(buf)
    assert msg["method"] == "test"
    assert msg["payload"] == {"a": 45, "b": "stuff"}

def test_end_to_end():
    s0, s1 = socket.socketpair()
    c0, c1 = RpcConnection(s0), RpcConnection(s1)

    my_result = None

    def handler(conn, d):
        nonlocal my_result, s1
        my_result = d
        s0.close()

    c0.register_method("test", ExampleData, None)
    c1.register_method("test", ExampleData, handler)

    c1.runserver()

    c0.send("test", ExampleData(5, "hello"))

    c1.server_thread.join(1.0)
    assert not c1.server_thread.is_alive()

    assert my_result.a == 5
    assert my_result.b == "hello"

