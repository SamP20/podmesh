import podman
from podmesh import PodMesh, Container, hookimpl
import threading
import pprint

BASE_URI = "unix:///run/podman/podman.sock"


def podman_listen(pm: PodMesh):
    pp = pprint.PrettyPrinter()
    client: podman.PodmanClient = pm.podman_client
    for evt in client.events(decode=True):
        print("============")
        pp.pprint(evt)


@hookimpl
def on_podmesh_created(pm: PodMesh):
    pm.podman_client = podman.PodmanClient(base_url=BASE_URI)


@hookimpl
def on_podmesh_ready(pm: PodMesh):
    pm.podman_poll_thread = threading.Thread(target=podman_listen, args=(pm,))
    pm.podman_poll_thread.daemon = True
    pm.podman_poll_thread.run()
