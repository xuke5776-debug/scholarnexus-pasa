import argparse, os
from .app import serve

ap = argparse.ArgumentParser(prog="scholarnexus.server")
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--port", type=int, default=8080)
ap.add_argument("--profile", default=None, choices=["cloud", "local", "offline"])
a = ap.parse_args()
if a.profile:
    os.environ["SN_PROFILE"] = a.profile
serve(a.host, a.port)
