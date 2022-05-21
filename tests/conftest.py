import pytest
from podmesh import PodMesh, hookspecs
import pluggy

@pytest.fixture
def podmesh_plugin_manager():
    plugin_manager = pluggy.PluginManager("podmesh")
    plugin_manager.add_hookspecs(hookspecs)
    return plugin_manager


@pytest.fixture
def podmesh_instance(podmesh_plugin_manager):
    return PodMesh(podmesh_plugin_manager.hook)
