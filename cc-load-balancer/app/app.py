"""Small Flask service used to demonstrate load balancing.

Every container runs this same code. Each one reports its own INSTANCE_NAME,
and all of them write hit counts to a shared Redis, so you can SEE requests
being spread across instances (and the counts stay consistent across them).
"""
import os
import socket

from flask import Flask, jsonify, render_template


class MemoryStore:
    """In-memory fallback (used for local runs without Redis and in tests)."""

    def __init__(self):
        self.hits = {}

    def incr(self, instance):
        self.hits[instance] = self.hits.get(instance, 0) + 1
        return self.hits[instance]

    def all(self):
        return dict(self.hits)

    def reset(self):
        self.hits.clear()


class RedisStore:
    """Shared store so every instance sees the same counters."""

    KEY = "lb:hits"

    def __init__(self, url):
        import redis

        self.r = redis.Redis.from_url(url, decode_responses=True)

    def incr(self, instance):
        return int(self.r.hincrby(self.KEY, instance, 1))

    def all(self):
        return {k: int(v) for k, v in self.r.hgetall(self.KEY).items()}

    def reset(self):
        self.r.delete(self.KEY)


def create_app(store=None):
    app = Flask(__name__)
    instance = os.getenv("INSTANCE_NAME", socket.gethostname())

    if store is None:
        url = os.getenv("REDIS_URL")
        store = RedisStore(url) if url else MemoryStore()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify(status="ok", instance=instance)

    @app.get("/api/whoami")
    def whoami():
        mine = store.incr(instance)
        total = sum(store.all().values())
        return jsonify(
            instance=instance,
            hostname=socket.gethostname(),
            instance_hits=mine,
            total_hits=total,
        )

    @app.get("/api/stats")
    def stats():
        hits = store.all()
        return jsonify(hits=hits, total=sum(hits.values()))

    @app.post("/api/reset")
    def reset():
        store.reset()
        return jsonify(status="reset")

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="not found"), 404

    return app
