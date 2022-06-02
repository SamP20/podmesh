# podmesh
Mesh networking system for podman

## Testing

There are two possible ways to run the tests: inside the devcontainer, or using the `Containerfile.test` image.

### Using the devcontainer

Podman is preferred on the host as this prevents privilege escalation even with the `--privileged` flag (required for wireguard and nested podman)

1. Start the devcontainer within VSCode
2. Run `pytest tests/` to run all the tests

### Using the test containerfile

This is what the CI uses and doesn't require podman in podman, however you can only run a subset of the tests inside (the rest have to be run on the host)

To run the non-podman tests:

1. Build the `Containerfile` image with `podman build -t podmesh -f Containerfile`
2. Build the `Containerfile.test` image with `podman build -t podmesh-test --build-arg FROM=podmesh -f Containerfile.test`
3. Run the non-podman tests with `podman run -it --rm podmesh-test pytest tests/` (TODO add test markers)

The podman tests can be run locally. This will create a few containers during the test, but they should be cleaned up by the end. To run these:

1. Run `pytest tests/` (TODO add test markers)