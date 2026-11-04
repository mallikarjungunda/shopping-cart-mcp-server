import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastmcp import Client

from shopping_cart_mcp.config import Settings
from shopping_cart_mcp.devtools import ALL_SCOPES, generate_keys, mint_token
from shopping_cart_mcp.mock_backend import create_app
from shopping_cart_mcp.server import build_server

SECRET = "x" * 40


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Serve(threading.Thread):
    def __init__(self, app, port):
        super().__init__(daemon=True)
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))

    def run(self):
        self.server.run()

    def start_and_wait(self):
        self.start()
        for _ in range(200):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("server did not start")

    def stop(self):
        self.server.should_exit = True


@pytest.fixture(scope="session")
def env(tmp_path_factory):
    d = tmp_path_factory.mktemp("keys")
    priv, pub = generate_keys(d)
    bport, mport = free_port(), free_port()
    backend_app = create_app(SECRET, approval_delay=0.3, credit={"bob": 100.0})
    backend = Serve(backend_app, bport).start_and_wait()
    s = Settings(backend_url=f"http://127.0.0.1:{bport}/shoppingcart/api", backend_secret=SECRET,
                 public_url=f"http://127.0.0.1:{mport}", dev_public_key_file=str(pub))
    from shopping_cart_mcp.auth import build_verifier
    mcp = build_server(s, verifier=build_verifier(s))
    srv = Serve(mcp.http_app(path="/mcp"), mport).start_and_wait()
    yield {"url": f"http://127.0.0.1:{mport}", "settings": s, "store": backend_app.state.store,
           "private": Path(priv).read_text()}
    srv.stop()
    backend.stop()


@pytest.fixture
def token(env):
    def make(user="alice", scopes=None, **kw):
        return mint_token(env["private"], user, scopes=scopes, issuer=env["settings"].issuer,
                          audience=env["settings"].audience, **kw)
    return make


@pytest.fixture
def connect(env, token):
    def make(user="alice", scopes=None):
        return Client(f"{env['url']}/mcp", auth=token(user, scopes))
    return make


@pytest.fixture(autouse=True)
def reset(env):
    st = env["store"]
    with st.lock:
        st.carts.clear(); st.orders.clear(); st.idem.clear()
        for p in st.products.values():
            p["stock"] = {"101": 25, "102": 40, "103": 15, "104": 8, "105": 5, "106": 30, "107": 200, "108": 0}[p["productId"]]
    yield
