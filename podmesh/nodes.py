import argparse
import logging
import socket
import time
from base64 import b64decode
from contextlib import suppress
from threading import Thread

from attrs import define
from pyroute2 import NDB, WireGuard

from podmesh import Hook, RpcConnection

WG_IFNAME = "wg-podmesh"
SERVER_PORT = 51935

logger = logging.getLogger(__name__)


@define
class Endpoint:
    ip: str
    port: int


@define
class WgConnectionInfo:
    pubkey: str
    cidr: str
    networks: list[str]
    endpoints: dict[str, Endpoint]


@define
class Node:
    name: str
    wg_conninfo: WgConnectionInfo


class WgManager:
    def __init__(self, ip: str, networks: list[str], private_key: str, wg_ifname=WG_IFNAME, wg_listen_port=51820):
        self.networks = networks
        self.ndb = NDB()
        self.wg = WireGuard()
        self.wg_ifname = wg_ifname
        if not self.ndb.interfaces.exists(self.wg_ifname):
            cluster_subnet = ip.split("/")[0] + "/16"
            (
                self.ndb.interfaces.create(ifname=self.wg_ifname, kind="wireguard")
                .add_ip(cluster_subnet)
                .set("state", "up")
                .commit()
            )

            self.wg.set(self.wg_ifname, private_key=private_key, listen_port=wg_listen_port)
            logger.debug(f"Created wireguard interface {self.wg_ifname} with address {cluster_subnet}")

        iface = self.wg.info(self.wg_ifname)[0]
        self.pubkey: str = iface.get_attr("WGDEVICE_A_PUBLIC_KEY").decode(encoding="ascii")
        logging.info(f"This node's wireguard public key is '{self.pubkey}'")

    def find_common_network(self,  wg_conninfo: WgConnectionInfo):
        our_networks = self.networks
        their_networks = wg_conninfo.networks
        for network in our_networks:
            if network in their_networks:
                break
        else:
            return None
        return network


    def update_wg_peer(self, wg_conninfo: WgConnectionInfo):
        peer = {}
        peer['public_key'] = wg_conninfo.pubkey
        peer['allowed_ips'] = [wg_conninfo.cidr]
        peer['persistent_keepalive'] = 15

        network = self.find_common_network(wg_conninfo)
        if network is None:
            raise RuntimeError("Peer does not share any common networks")

        with suppress(KeyError):
            endpoint = wg_conninfo.endpoints[network]
            peer["endpoint_addr"] = endpoint.ip
            peer["endpoint_port"] = endpoint.port
            logger.debug(f"found endpoint {endpoint} for peer '{wg_conninfo.pubkey}'")


        self.wg.set(self.wg_ifname, peer=peer)
        logger.debug(f"Updated wireguard info for peer '{wg_conninfo.pubkey}'")

    def get_peerinfo(self, wg_conninfo: WgConnectionInfo):
        pubkey = wg_conninfo.pubkey

        peers = self.wg.info(self.wg_ifname)[0].get_attr("WGDEVICE_A_PEERS")
        if not peers:
            return None

        for peer in peers:
            if peer.get_attr("WGPEER_A_PUBLIC_KEY").decode() == pubkey:
                return peer
        return None


class NodeManager:
    def __init__(self, name: str, ip: str, networks: list[str], private_key: str, **kwargs):
        self.wg = WgManager(ip, networks, private_key, **kwargs)

        this_wg = WgConnectionInfo(self.wg.pubkey, ip, networks, {})
        self.this_node = Node(name, this_wg)
        self.connections_to_poll: list[WgConnectionInfo] = []

        self.node_connections: dict[str, RpcConnection] = {}
        self.on_connection_created = Hook()

    def run(self):
        self.srv = self.run_server(self.this_node.wg_conninfo.cidr)
        self.client_poller = self.run_client_poller()

    def add_peer(self, wg_conninfo: WgConnectionInfo):
        self.wg.update_wg_peer(wg_conninfo)
        if self.compare_keys(wg_conninfo.pubkey, self.this_node.wg_conninfo.pubkey):
            logger.info(f"Added peer to poll {wg_conninfo}")
            self.connections_to_poll.append(wg_conninfo)

    def compare_keys(self, k1, k2):
        k1_val = int.from_bytes(b64decode(k1), 'big')
        k2_val = int.from_bytes(b64decode(k2), 'big')
        return (k1_val - k2_val) & (1<<255) > 0

    def run_server(self, ip: str):
        addr = ip.split("/")[0]
        server_socket = socket.create_server((addr, SERVER_PORT))
        def run_thread():
            logger.debug("Running server thread")
            while True:
                client_socket, address = server_socket.accept()
                logger.info(f"Server got connection {address}")
                self.setup_connection(client_socket, address[0])
        thread = Thread(target=run_thread)
        thread.daemon = True
        thread.start()
        return thread

    def run_client_poller(self):
        def run_thread():
            logger.debug("Running client poll thread")
            while True:
                time.sleep(2.0)
                for conn in self.connections_to_poll:
                    addr = conn.cidr.split("/")[0]
                    port = SERVER_PORT
                    try:
                        client_socket = socket.create_connection((addr, port), timeout=2.0)
                        self.connections_to_poll.remove(conn)
                        logger.info(f"Client got connection {(addr, port)}")
                        self.setup_connection(client_socket, addr)
                    except Exception:
                        pass
        thread = Thread(target=run_thread)
        thread.daemon = True
        thread.start()
        return thread

    def setup_connection(self, socket: socket.socket, addr: str):
        rpc_conn = RpcConnection(socket)
        rpc_conn.register_method("identify", Node, self.identify_connection)
        rpc_conn.register_method("nodeinfo", Node, self.update_nodeinfo)
        rpc_conn.register_method("endpoint", Endpoint, self.update_endpoint)

        rpc_conn.runserver()
        rpc_conn.send("identify", self.this_node)

    def identify_connection(self, conn: RpcConnection, node: Node):
        logger.debug(f"RPC method 'identify' called from peer {node.name}")
        conn.node = node
        if node.name not in self.node_connections:
            logger.debug(f"Adding peer {node.name} to known connections")
            self.node_connections[node.name] = conn
            self.on_connection_created(conn)
        else:
            # Sometimes a node may identify again to share its wg_conninfo
            # As an example, node A connects to node B and discovers it's public IP.
            # Node A can then re-identify with it's peers to let them know of it's newly
            # discovered IP
            logger.debug(f"Updating connection info for peer {node.name}")
            existing_node = self.node_connections[node.name].node
            existing_node.wg_conninfo = node.wg_conninfo

        peer = self.wg.get_peerinfo(node.wg_conninfo)
        if not peer:
            return

        endpoint = peer.get_attr("WGPEER_A_ENDPOINT")
        if endpoint:
            ep = Endpoint(endpoint["addr"], endpoint["port"])
            logger.debug(f"Notifying {node.name} of their endpoint {ep}")
            conn.send("endpoint", ep)


    def update_nodeinfo(self, conn: RpcConnection, node: Node):
        if node.name not in self.node_connections:
            logger.debug(f"Adding potential new peer {node.name}")
            self.add_peer(node.wg_conninfo)

    def update_endpoint(self, conn: RpcConnection, ep: Endpoint):
        logger.debug(f"Peer {conn.node.name} told us our endpoint {ep}")
        wg_conninfo = self.this_node.wg_conninfo
        network = self.wg.find_common_network(conn.node.wg_conninfo)
        if network in wg_conninfo.endpoints:
            existing = wg_conninfo.endpoints[network]
            if existing == ep:
                return

        # Our endpoint has changed. Update it
        logger.debug(f"Endpoint for network {network} has changed to {ep}")
        wg_conninfo.endpoints[network] = ep

        # Tell other nodes about our new endpoint
        for rsp_conn in self.node_connections.values():
            # Don't need to notify the connection that just notified us
            if rsp_conn == conn:
                continue
            logger.debug(f"Notifying {rsp_conn.node.name} of our new endpoint")
            rsp_conn.send("identify", self.this_node)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run node server only.")
    parser.add_argument("name", help="Node name.")
    parser.add_argument("ip", help="Node subnet. Should be a slice of a /16.")
    parser.add_argument("private_key", help="base64 wireguard private key of node.")
    parser.add_argument("--network", action="append", help="List of networks in order that this node belongs to.")
    parser.add_argument("--ifname", default=WG_IFNAME, help="Wireguard interface name.")
    parser.add_argument("--port", default=51820, type=int, help="Wireguard listen port.")
    parser.add_argument('--verbose', "-v", action='count', default=0, help="Increase log verbosity.")

    args = parser.parse_args()

    if args.verbose == 0:
        level = logging.WARN
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    logging.basicConfig(level=level)


    nm = NodeManager(args.name, args.ip, args.network, args.private_key, wg_ifname=args.ifname, wg_listen_port=args.port)
    nm.run()

    nm.srv.join()