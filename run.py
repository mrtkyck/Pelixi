import os

from app.server import run_server


if __name__ == "__main__":
    host = os.getenv("MYNOTES_HOST", "127.0.0.1")
    port = int(os.getenv("MYNOTES_PORT", "8000"))
    run_server(host=host, port=port)
