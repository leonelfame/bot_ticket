import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from zone_availability_parser import parse_zone_availability_file, summarize_zones


APP_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = APP_DIR / "fixtures" / "zonesavail_sample.html"


def zone_to_dict(zone):
    return {
        "flow": zone.flow,
        "zone": zone.code,
        "label": zone.label,
        "availability": zone.availability,
        "available_count": zone.available_count,
        "is_available": zone.is_available,
    }


def load_availability(source: Path) -> dict:
    zones = parse_zone_availability_file(source)
    return {
        "source": str(source),
        "summary": summarize_zones(zones),
        "zones": [zone_to_dict(zone) for zone in zones],
    }


class AvailabilityHandler(BaseHTTPRequestHandler):
    source = DEFAULT_SOURCE

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True})
            return

        if parsed.path == "/availability":
            query = parse_qs(parsed.query)
            source = Path(query.get("source", [str(self.source)])[0])
            if not source.is_absolute():
                source = (APP_DIR / source).resolve()
            try:
                payload = load_availability(source)
            except OSError as error:
                self._send_json({"ok": False, "error": str(error)}, status=404)
                return
            self._send_json({"ok": True, **payload})
            return

        self._send_json(
            {
                "ok": False,
                "error": "not found",
                "routes": ["/health", "/availability?source=fixtures/zonesavail_sample.html"],
            },
            status=404,
        )

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local availability API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    if not source.is_absolute():
        source = (APP_DIR / source).resolve()

    AvailabilityHandler.source = source
    server = ThreadingHTTPServer((args.host, args.port), AvailabilityHandler)
    print(f"Serving availability API on http://{args.host}:{args.port}")
    print(f"Default source: {source}")
    server.serve_forever()


if __name__ == "__main__":
    main()
