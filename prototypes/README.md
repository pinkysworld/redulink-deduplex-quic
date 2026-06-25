# Minimal Socket Prototype

This prototype demonstrates ReduLink endpoint cooperation over a localhost TCP
socket. The client encodes an update as modeled `FULL` and `REF` frames using a
warm dictionary. The server receives those frames, reconstructs the payload, and
writes the byte-exact output.

It is intentionally not a QUIC implementation. It does not implement packet
loss recovery, cryptographic authentication, replay windows, transport
parameters, or production privacy controls.

Run the self-contained demo:

```bash
python3 prototypes/redulink_socket_prototype.py demo
```

Manual two-terminal run:

```bash
python3 prototypes/redulink_socket_prototype.py server \
  --warm /path/to/warm.bin \
  --output /tmp/redulink.out \
  --port 9876
```

```bash
python3 prototypes/redulink_socket_prototype.py client \
  --warm /path/to/warm.bin \
  --input /path/to/update.bin \
  --port 9876
```

The prototype is included to move the artifact beyond an offline-only model. It
should be described in the paper as an endpoint reconstruction prototype, not as
a deployed transport.
