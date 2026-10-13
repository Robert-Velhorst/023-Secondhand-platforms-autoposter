"""Local-only ngrok process fixture: records arguments and emits controlled logs."""

import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

arguments = sys.argv[1:]
upstream = urlsplit(arguments[1])
with socket.socket() as probe:
    try:
        probe.bind((upstream.hostname, upstream.port))
        owned = False
    except OSError:
        owned = True
Path(os.environ["NGROK_TEST_RECORD"]).write_text(json.dumps({"args": arguments, "port_owned": owned}))
mode = os.environ.get("NGROK_TEST_MODE", "ready")
if mode == "exit":
    print("controlled ngrok fixture error", flush=True)
    raise SystemExit(19)
if mode != "silent":
    print(json.dumps({"msg": "unrelated", "url": "https://wrong.example"}), flush=True)
    print(json.dumps({"msg": "started tunnel", "addr": arguments[1],
                      "url": os.environ.get("NGROK_TEST_URL", "https://owned.example")}), flush=True)
time.sleep(60)
