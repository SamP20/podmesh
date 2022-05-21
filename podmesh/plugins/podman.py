import podman
from podmesh import PodMesh, Container, hookimpl
import threading
import pprint

BASE_URI = "unix:///run/podman/podman.sock"


def podman_listen(pm: PodMesh):
    pp = pprint.PrettyPrinter()
    client: podman.PodmanClient = pm.podman_client
    for evt in client.events(decode=True):
        match evt:
            case {'Action': 'create', 'Type': 'container', 'Actor': actor}:
                name = actor["Attributes"]["name"]
                labels = actor["Attributes"].copy()
                labels.pop('containerExitCode', None)
                labels.pop('image', None)
                labels.pop('name', None)
                c = Container(actor["ID"], name, labels)
                pm.add_container(c)
            case {'Action': 'remove', 'Type': 'container', 'Actor': actor}:
                try:
                    c = pm.containers[actor["ID"]]
                    pm.remove_container(c)
                except KeyError:
                    pass


@hookimpl
def on_podmesh_created(pm: PodMesh):
    pm.podman_client = podman.PodmanClient(base_url=BASE_URI)


@hookimpl
def on_podmesh_ready(pm: PodMesh):
    pm.podman_poll_thread = threading.Thread(target=podman_listen, args=(pm,))
    pm.podman_poll_thread.daemon = True
    pm.podman_poll_thread.run()


@hookimpl
def on_container_created(pm: PodMesh, container: Container):
    print(f"Added {container}")


@hookimpl
def on_container_removed(pm: PodMesh, container: Container):
    print(f"Removed {container}")