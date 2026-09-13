"""Local process measurements; contains no message text or remote telemetry."""
import sys
import time

try:
    import resource
except ImportError:  # The application also runs on Windows.
    resource = None


def start_measurement():
    return {"cpu_started": time.process_time(), "wall_started": time.perf_counter()}


def finish_measurement(start, package):
    wall = max(0.0, time.perf_counter() - start["wall_started"])
    cpu = max(0.0, time.process_time() - start["cpu_started"])
    peak = None
    if resource is not None:
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = int(value if sys.platform == "darwin" else value * 1024)
    checks = package.verification
    verified = (package.status == "answered" and bool(checks)
                and all(check.get("passed") is True for check in checks))
    return {"wall_seconds": wall, "cpu_seconds": cpu, "process_peak_rss_bytes": peak,
            "memory_scope": "process lifetime high-water mark; not per-turn allocation",
            "measurement_scope": "through rendering, before final persistence",
            "verified_solution": verified,
            "wall_seconds_per_verified_solution": wall if verified else None,
            "monetary_cost": None,
            "cost_scope": "local measured compute; provider billing unavailable"}
