from prometheus_client import Gauge, Counter
from contextlib import contextmanager


active_conns = Gauge(
    "replayserver_active_connections_count",
    "Count of currently active connections.",
    ["category"])
served_conns = Counter(
    "replayserver_served_connections_total",
    "How many connections we served to completion.",
    ["result"])

running_replays = Gauge(
    "replayserver_running_replays_count",
    "Count of currently running replays.")
finished_replays = Counter(
    "replayserver_finished_replays_total",
    "Number of replays ran to completion.")
saved_replays = Counter(
    "replayserver_saved_replay_files_total",
    "Total replays successfully saved to disk.")


@contextmanager
def track(metric):
    try:
        metric.inc()
        yield
    finally:
        metric.dec()
