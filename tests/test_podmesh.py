from uuid import uuid4
from podmesh import Container


def test_add_remove_container(podmesh_instance):
    c = Container(uuid4(), "my_container")
    podmesh_instance.add_container(c)
    assert podmesh_instance.containers[c.id] == c
    podmesh_instance.remove_container(c)
    assert c.id not in podmesh_instance.containers


def test_add_remove_container_labels(podmesh_instance):
    c = Container(uuid4(), "my_container", {"my_label": "my_value"})
    podmesh_instance.add_container(c)
    assert c in podmesh_instance.labels["my_label"]
    podmesh_instance.remove_container(c)
    assert c not in podmesh_instance.labels["my_label"]
