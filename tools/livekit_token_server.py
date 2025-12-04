#!/usr/bin/env python3
"""
Simple LiveKit token server helper

Usage:
 1) Install dependencies into your venv:
    pip install flask livekit-server-sdk

 2) Export your LiveKit API key/secret in the shell (PowerShell example):
    $env:LIVEKIT_API_KEY = 'API7S2PuKyk3qPv'
    $env:LIVEKIT_API_SECRET = 'xHTgDzsKY18fjdm21IG3xSTdWyZwsxXcVjfqiIeDieuC'

 3) Run the server:
    python tools\livekit_token_server.py

 4) Get a token (example):
    curl "http://127.0.0.1:5000/getToken?room=demo-room&identity=alice"

This returns a JWT you can use from the frontend to connect to the LiveKit room.

Security note: Do NOT commit your API secret into source control. Use environment variables
or a secrets manager in production.
"""
import os
from flask import Flask, request, jsonify

try:
    # `livekit-server-sdk` provides the AccessToken helper
    from livekit import api
except Exception:  # pragma: no cover - helpful error message if the package is missing
    api = None

app = Flask(__name__)


def make_token(room: str, identity: str, ttl_seconds: int = 600) -> str:
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in the environment")

    if api is None:
        raise RuntimeError("livekit-server-sdk package not installed. Run: pip install livekit-server-sdk")

    token = api.AccessToken(api_key, api_secret) \
        .with_identity(identity) \
        .with_name(identity) \
        .with_grants(api.VideoGrants(room_join=True, room=room))

    return token.to_jwt()


@app.route("/getToken")
def get_token_route():
    room = request.args.get("room", "demo-room")
    identity = request.args.get("identity") or request.args.get("user") or "anon"
    try:
        jwt = make_token(room=room, identity=identity)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500

    return jsonify({"token": jwt, "room": room, "identity": identity})


if __name__ == "__main__":
    host = os.getenv("LIVEKIT_TOKEN_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("LIVEKIT_TOKEN_SERVER_PORT", "5000"))
    print("LiveKit token server starting on http://%s:%d" % (host, port))
    print("Make sure LIVEKIT_API_KEY and LIVEKIT_API_SECRET are set in your environment.")
    app.run(host=host, port=port)
