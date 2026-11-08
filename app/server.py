
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import redis  

PORT = int(os.environ.get("PORT", "3033"))


REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

db = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            self._reply(200, "OK")
        elif self.path == "/visits":
            try:
                count = db.incr("visits")   
                self._reply(200, f"Visits: {count}")
            except redis.RedisError as error:
                self._reply(503, f"Redis unavailable: {error}")
        else:
            self._reply(404, "Not Found")

    def _reply(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Web server on port {PORT}, Redis at {REDIS_HOST}:{REDIS_PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
