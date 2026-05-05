import os

from app.server import run_server


if __name__ == "__main__":
    cloud_port = (os.getenv("PORT") or "").strip()
    configured_port = (
        cloud_port
        or os.getenv("PELIXI_PORT")
        or os.getenv("MYNOTES_PORT")
        or "8000"
    )
    host = (
        os.getenv("PELIXI_HOST")
        or os.getenv("MYNOTES_HOST")
        or ("0.0.0.0" if cloud_port else "127.0.0.1")
    )
    port = int(configured_port)
    run_server(host=host, port=port)
