import json
from wsgiref.simple_server import make_server

from app.api.routes import handle_request
from app.core.logging import configure_logging

configure_logging()


def app(environ, start_response):
    method = environ["REQUEST_METHOD"]
    path = environ.get("PATH_INFO", "")
    headers = {
        key[5:].replace("_", "-"): value
        for key, value in environ.items()
        if key.startswith("HTTP_")
    }
    content_length = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ["wsgi.input"].read(content_length) if content_length > 0 else b""

    status_code, response_headers, payload = handle_request(method, path, headers, body)
    start_response(f"{status_code} {'OK' if status_code < 400 else 'ERROR'}", response_headers)
    return [json.dumps(payload).encode("utf-8")]


if __name__ == "__main__":
    with make_server("127.0.0.1", 8000, app) as server:
        print("Serving on http://127.0.0.1:8000")
        server.serve_forever()
