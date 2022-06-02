# podmesh
Mesh networking system for podman

## Developing

A devcontainer is provided to keep your environment isolated from the host when developing and running Podmesh.

Also included is a `containerfile.dev` image which allows you to run multiple instances of Podmesh for testing meshing behaviour for example.
The dev image can automatically use your current files by creating the following volume `-v ./:/src/:rw`. This image should also be run
with the `--privileged` flag to allow the container to create wireguard interfaces. There is a limitation when using the `containerfile.dev`
inside the devcontainer as any interfaces created will be visible in both containers.

## Testing

There are two possible ways to run the tests: inside the devcontainer, or using either of the `Containerfile.*` images.

### Using the devcontainer

Podman is preferred on the host as this prevents privilege escalation even with the `--privileged` flag (required for wireguard and nested podman)

1. Start the devcontainer within VSCode
2. Run `pytest tests/` to run all the tests

### Using the test containerfile

This is what the CI uses and doesn't require podman in podman, however you can only run a subset of the tests inside (the rest have to be run on the host)

To run the non-podman tests:

2. Build the `Containerfile.dev` image with `podman build -t podmesh-test -f Containerfile.dev`. This only needs doing once
3. Run the non-podman tests with `podman run --privileged -it --rm -v ./:/src/:rw podmesh-test pytest tests/` (TODO add test markers)

The podman tests can be run locally. This will create a few containers during the test, but they should be cleaned up by the end. To run these:

1. Run `pytest tests/` (TODO add test markers)