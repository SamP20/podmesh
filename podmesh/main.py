import pluggy
from podmesh import hookspecs, PodMesh
from podmesh.plugins import podman as podmesh_podman
from time import sleep


def main():
    plugin_manager = get_plugin_manager()
    podmesh = PodMesh(plugin_manager.hook)

    podmesh.ready()

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("Exiting")

    podmesh.exit()


def get_plugin_manager():
    plugin_manager = pluggy.PluginManager("podmesh")
    plugin_manager.add_hookspecs(hookspecs)
    plugin_manager.load_setuptools_entrypoints("podmesh")
    return plugin_manager


if __name__ == "__main__":
    main()
