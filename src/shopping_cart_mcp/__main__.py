from .config import Settings
from .server import build_server


def main() -> None:
    s = Settings.from_env()
    build_server(s).run(transport="http", host=s.host, port=s.port)


if __name__ == "__main__":
    main()
