#!/usr/bin/env python3
"""Small client to send commands to the run_all UNIX socket.

Usage:
  python3 tools/ipc_addtruck.py addtruck 2 routes/example.route
  python3 tools/ipc_addtruck.py list
"""
import sys
import socket
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOCKET = str(ROOT / "run_all.sock")

def send(cmd: str):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCKET)
    s.sendall((cmd + "\n").encode())
    data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
        if b"\n" in chunk:
            break
    s.close()
    try:
        print(json.dumps(json.loads(data.decode()), indent=2))
    except Exception:
        print(data.decode())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = " ".join(sys.argv[1:])
    send(cmd)


if __name__ == "__main__":
    main()
