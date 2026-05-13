import os

from app.server import run_server


if __name__ == "__main__":
    # Render ve benzeri platformlar PORT verir; dis trafigin gelmesi icin host mutlaka 0.0.0.0 olmalidir.
    # MYNOTES_HOST/PELIXI_HOST ile 127.0.0.1 verilirse Render disardan baglanamaz.
    cloud_port = (os.getenv("PORT") or "").strip()
    if cloud_port:
        host = "0.0.0.0"
        port = int(cloud_port)
    else:
        host = os.getenv("MYNOTES_HOST") or os.getenv("PELIXI_HOST") or "127.0.0.1"
        configured = os.getenv("MYNOTES_PORT") or os.getenv("PELIXI_PORT") or "8000"
        port = int(configured)
    run_server(host=host, port=port)
