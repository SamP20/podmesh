import pytest
from pr2modules.ndb.main import NDB
from pr2modules.netlink.generic.wireguard import WireGuard
from podmesh.nodes import WG_IFNAME, Endpoint, WgConnectionInfo, WgManager, NodeManager

@pytest.fixture
def ndb():
    return NDB()

@pytest.fixture
def wg():
    return WireGuard()


@pytest.fixture
def remove_interface(ndb):
    if ndb.interfaces.exists(WG_IFNAME):
        ndb.interfaces[WG_IFNAME].remove().commit()

    yield

    if ndb.interfaces.exists(WG_IFNAME):
        ndb.interfaces[WG_IFNAME].remove().commit()

# Example keys
PRIVATE_EXAMPLE_KEY = "qM1JpOvogLsS+3Xn6TBM8g45jwCAG2CtvnmnDB+RPl8="
PUBLIC_EXAMPLE_KEY = "n0rirLNsvIUQBQa4cIWi+yoiiEohXGQssNp2POGzoX0="

def test_wg_manager_init(ndb: NDB, wg: WireGuard, remove_interface):
    wgm = WgManager("10.97.0.1/24", ["public"], PRIVATE_EXAMPLE_KEY)

    assert ndb.interfaces.exists(WG_IFNAME)
    iface = ndb.interfaces[WG_IFNAME]
    assert iface["kind"] == "wireguard"
    assert iface.ipaddr.exists("10.97.0.1/16")

    wginfo = wg.info(WG_IFNAME)[0]
    assert wginfo.get_attr("WGDEVICE_A_PRIVATE_KEY").decode() == PRIVATE_EXAMPLE_KEY


def test_wg_manager_create_peer(wg: WireGuard, remove_interface):
    wgm = WgManager("10.97.0.1/24", ["public"], PRIVATE_EXAMPLE_KEY)

    wg_conninfo = WgConnectionInfo(
        pubkey=PUBLIC_EXAMPLE_KEY,
        cidr="10.97.1.1/24",
        networks=["public"],
        endpoints={}
    )

    wgm.update_wg_peer(wg_conninfo)

    wginfo = wg.info(WG_IFNAME)[0]
    peers = wginfo.get_attr("WGDEVICE_A_PEERS")
    assert len(peers) == 1
    peer = peers[0]

    assert peer.get_attr("WGPEER_A_PUBLIC_KEY").decode() == PUBLIC_EXAMPLE_KEY
    allowed_ips = peer.get_attr("WGPEER_A_ALLOWEDIPS")
    assert len(allowed_ips) == 1
    allowed_ip = allowed_ips[0]
    assert allowed_ip.get_attr("WGALLOWEDIP_A_IPADDR") == "0a:61:01:00"
    assert allowed_ip.get_attr("WGALLOWEDIP_A_CIDR_MASK") == 24


def test_wg_manager_update_peer_endpoint(wg: WireGuard, remove_interface):
    wgm = WgManager("10.97.0.1/24", ["public"], PRIVATE_EXAMPLE_KEY)

    wg_conninfo = WgConnectionInfo(
        pubkey=PUBLIC_EXAMPLE_KEY,
        cidr="10.97.1.1/24",
        networks=["public"],
        endpoints={}
    )
    wgm.update_wg_peer(wg_conninfo)

    # This is a non-routable IP only to be used for documentation (RFC 5737)
    wg_conninfo.endpoints["public"] = Endpoint("192.0.2.0", 52036)

    wgm.update_wg_peer(wg_conninfo)

    wginfo = wg.info(WG_IFNAME)[0]
    peers = wginfo.get_attr("WGDEVICE_A_PEERS")
    assert len(peers) == 1
    peer = peers[0]

    ep = peer.get_attr("WGPEER_A_ENDPOINT")
    assert ep["port"] == 52036
    assert ep["addr"] == "192.0.2.0"

def test_wg_manager_get_peerinfo(wg: WireGuard, remove_interface):
    wgm = WgManager("10.97.0.1/24", ["public"], PRIVATE_EXAMPLE_KEY)

    wg_conninfo = WgConnectionInfo(
        pubkey=PUBLIC_EXAMPLE_KEY,
        cidr="10.97.1.1/24",
        networks=["public"],
        endpoints={}
    )
    wgm.update_wg_peer(wg_conninfo)

    peer = wgm.get_peerinfo(wg_conninfo)
    assert peer.get_attr("WGPEER_A_PUBLIC_KEY").decode() == PUBLIC_EXAMPLE_KEY


def test_compare_keys(remove_interface):
    nm = NodeManager("my_node", "10.97.0.1/24", ["public"], PRIVATE_EXAMPLE_KEY)

    k1 = "8Jlu8unT1fCGpQZXHrONC4y//TBEsuiw7X5KaO50Wmc="
    k2 = "uMkycgFmoOIP61/+8V0OJLRTxOEDlTj/EOS2nstJWn8="

    cmp1 = nm.compare_keys(k1, k2)
    cmp2 = nm.compare_keys(k2, k1)
    assert cmp1 != cmp2