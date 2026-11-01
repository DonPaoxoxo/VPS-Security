"""CLI entrypoint for Docker's HEALTHCHECK. Run as `python -m worker.healthcheck`.

Deliberately a separate, fresh process (as every `docker exec`-based
healthcheck is) — it has no access to the running worker's memory, so it
reads the health file that process writes to instead. Exits 0 if every
scheduled job is both running on schedule and not repeatedly failing; exits 1
and prints the reason otherwise, so `docker inspect` / `docker compose ps`
reflects actual job health, not just "the python process exists."
"""

import sys

from worker.health import evaluate_health_file


def main() -> int:
    healthy, detail = evaluate_health_file()
    if healthy:
        print(f"healthy: {detail}")
        return 0
    print(f"unhealthy: {detail}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
