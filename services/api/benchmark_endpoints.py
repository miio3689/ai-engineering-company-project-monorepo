"""Benchmark API endpoints for performance analysis and caching decisions.

Usage:
    python -m services.api.benchmark_endpoints --output-dir DIR [--calls N] [--volume small|large]

Measures endpoint response times with realistic load test data.
"""

import json
import logging
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch
import sqlite3

from fastapi.testclient import TestClient

from services.api.app.main import app

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class BenchmarkRunner:
    def __init__(self, output_dir: Path, volume: str = "small"):
        self.output_dir = Path(output_dir)
        self.volume = volume
        self.results = []
        
        # Determine data volume parameters
        if volume == "large":
            self.incidents_count = 5000
            self.suppliers_count = 500
            self.ingredients_count = 500
            self.movements_count = 50000
        else:  # small
            self.incidents_count = 500
            self.suppliers_count = 50
            self.ingredients_count = 50
            self.movements_count = 2000
    
    def setup_databases(self) -> tuple[str, str, Path, Path, Path, str]:
        """Setup temporary databases and return paths."""
        logger.info(f"\nSetting up {self.volume} volume test databases...")
        
        # Import and run seeder
        from . import seed_load
        
        incidents_path = self.output_dir / f"incidents_{self.volume}.json"
        suppliers_path = self.output_dir / f"suppliers_{self.volume}.json"
        auth_path = self.output_dir / f"auth_{self.volume}.json"
        inventory_db_url = f"sqlite:///{self.output_dir / f'inventory_{self.volume}.db'}"
        
        # Clean existing
        for p in [incidents_path, suppliers_path, auth_path, self.output_dir / f"inventory_{self.volume}.db"]:
            if p.exists():
                p.unlink()
        
        # Generate data
        seed_load.generate_incidents(incidents_path, self.incidents_count)
        from .models import Branch, Category, IncidentOrigin, IncidentStatus
        from tinydb import TinyDB

        enum_by_field = {
            "status": IncidentStatus,
            "category": Category,
            "origin": IncidentOrigin,
            "branch": Branch,
        }
        legacy_values = {
            "status": {"closed": IncidentStatus.resolved.value},
            "category": {
                "delivery_delay": "delivery_issue",
                "quality_concern": Category.other.value,
                "compliance": Category.other.value,
            },
            "origin": {
                "employee": "branch",
                "system": "internal",
            },
        }
        valid_branches = [branch.value for branch in Branch]
        with TinyDB(str(incidents_path)) as db:
            incidents = db.table("incidents")
            for record in incidents:
                changes = {}
                for field, enum_type in enum_by_field.items():
                    value = record[field]
                    valid_values = {item.value for item in enum_type}
                    if value in valid_values:
                        continue
                    replacement = legacy_values.get(field, {}).get(value)
                    if replacement is None and field == "branch":
                        replacement = valid_branches[
                            (record.doc_id - 1) % len(valid_branches)
                        ]
                    if replacement not in valid_values:
                        raise ValueError(
                            f"Seeder produced unsupported incident {field}: {value}"
                        )
                    changes[field] = replacement
                if changes:
                    incidents.update(changes, doc_ids=[record.doc_id])
        seed_load.generate_suppliers(suppliers_path, self.suppliers_count)
        os.environ["DATABASE_URL"] = inventory_db_url
        seed_load.generate_inventory(inventory_db_url, self.ingredients_count, self.movements_count)
        email, password = seed_load.create_test_user(auth_path)
        
        return email, password, incidents_path, suppliers_path, auth_path, inventory_db_url
    
    def get_table_counts(self) -> dict[str, int]:
        """Get row counts from every seeded TinyDB collection and SQL table."""
        counts = {}
        
        from tinydb import TinyDB

        with TinyDB(str(self.incidents_path)) as db:
            for table in ("incidents", "incident_seed_keys"):
                counts[table] = len(db.table(table).all())
        with TinyDB(str(self.suppliers_path)) as db:
            counts["suppliers"] = len(db.table("suppliers").all())
        with TinyDB(str(self.auth_path)) as db:
            for table in ("users", "profiles"):
                counts[table] = len(db.table(table).all())
        
        # SQLite counts
        inv_db_path = self.inventory_db_url.removeprefix("sqlite:///")
        with sqlite3.connect(inv_db_path) as conn:
            cursor = conn.cursor()
            for table in ("ingredient", "ingredient_entry", "ingredient_exit"):
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
        
        return counts
    
    def benchmark_endpoint(
        self,
        method: str,
        path: str,
        calls: int,
        client: TestClient,
        auth_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Discard one warm-up request, then measure every successful call."""
        def request_once():
            response = client.request(method, path, headers=auth_headers or {})
            if not 200 <= response.status_code < 300:
                raise RuntimeError(f"HTTP {response.status_code}")
            return response

        try:
            request_once()
        except Exception as exc:
            raise RuntimeError(
                f"Warm-up failed for {method} {path}: {exc}"
            ) from exc

        times = []
        
        for _ in range(calls):
            start = time.perf_counter()
            try:
                request_once()
            except Exception as e:
                raise RuntimeError(
                    f"Measured request {len(times) + 1}/{calls} failed "
                    f"for {method} {path}: {e}"
                ) from e
            times.append((time.perf_counter() - start) * 1000)

        ordered_times = sorted(times)
        p95_index = math.ceil(0.95 * len(ordered_times)) - 1
        
        return {
            "method": method,
            "path": path,
            "n": len(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "p95_ms": ordered_times[p95_index],
        }
    
    def run(self, calls: int = 10):
        """Run full benchmark suite."""
        calls = max(calls, 30)
        logger.info(f"\nRunning benchmark with {self.volume} volume data...")
        logger.info(f"Calls per endpoint: 1 discarded warm-up + {calls} measured")
        
        email, password, incidents_path, suppliers_path, auth_path, inventory_db_url = self.setup_databases()
        
        self.incidents_path = incidents_path
        self.suppliers_path = suppliers_path
        self.auth_path = auth_path
        self.inventory_db_url = inventory_db_url
        
        # Patch database paths and create client
        import services.api.database as db_module
        import services.api.services_auth as auth_module
        from services.api.auth_security import get_current_user
        from services.api.models import UserResponse, UserRole
        
        with patch.object(db_module, "INCIDENTS_DATABASE_PATH", incidents_path):
            with patch.object(db_module, "DATABASE_PATH", suppliers_path):
                with patch.object(auth_module, "AUTH_DATABASE_PATH", auth_path):
                    with patch.dict(os.environ, {"DATABASE_URL": inventory_db_url}):
                        # Override get_current_user
                        test_user = UserResponse(
                            id=1,
                            email=email,
                            is_active=True,
                            role=UserRole.user,
                            created_at="2026-01-01T00:00:00+00:00",
                        )
                        app.dependency_overrides[get_current_user] = lambda: test_user
                        
                        try:
                            with TestClient(app) as client:
                                # Authenticate
                                auth_response = client.post(
                                    "/auth/login",
                                    data={"username": email, "password": password}
                                )
                                auth_headers = {}
                                if auth_response.status_code == 200:
                                    token = auth_response.json()["access_token"]
                                    auth_headers = {"Authorization": f"Bearer {token}"}
                                    logger.info(f"Authenticated as {email}")
                                
                                # Endpoints to benchmark
                                endpoints = [
                                    ("GET", "/api/incidents", None),
                                    ("GET", "/api/incidents?status=open&origin=customer&branch=central", None),
                                    ("GET", "/api/incidents/summary", None),
                                    ("GET", "/suppliers", None),
                                    ("GET", "/inventory/products", None),
                                    ("GET", "/inventory/products/1", None),
                                    ("GET", "/inventory/orders", None),
                                    ("GET", "/auth/me", auth_headers),
                                    ("GET", "/profiles/me", auth_headers),
                                    ("GET", "/users", None),
                                ]
                                
                                logger.info(f"\nBenchmarking {len(endpoints)} endpoints with {calls} calls each...")
                                results = []
                                
                                for method, path, headers in endpoints:
                                    result = self.benchmark_endpoint(method, path, calls, client, headers)
                                    results.append(result)
                                    logger.info(f"  {method:4} {path:75} n={result['n']:3} | "
                                              f"mean: {result['mean_ms']:7.2f}ms | "
                                              f"median: {result['median_ms']:7.2f}ms | "
                                              f"p95: {result['p95_ms']:7.2f}ms")
                                
                                table_counts = self.get_table_counts()
                                # Print summary table
                                self.print_results_table(results, table_counts)
                                
                                return results
                        finally:
                            app.dependency_overrides.clear()
    
    def print_results_table(self, results: list[dict], table_counts: dict):
        """Print benchmark results as a formatted table."""
        logger.info("\n" + "="*120)
        logger.info(f"BENCHMARK RESULTS - {self.volume.upper()} VOLUME")
        logger.info("="*120)
        
        logger.info("\nDatabase State:")
        for table, count in table_counts.items():
            logger.info(f"  {table:20} {count:8} rows")
        
        logger.info("\nEndpoint Performance (milliseconds):")
        logger.info(f"{'Method':<6} {'Path':<70} {'n':>4} {'Min':>9} {'Mean':>9} {'Median':>9} {'P95':>9} {'Max':>9}")
        logger.info("-" * 135)
        
        for result in results:
            logger.info(
                f"{result['method']:<6} {result['path']:<70} {result['n']:>4} "
                f"{result['min_ms']:>9.2f} {result['mean_ms']:>9.2f} "
                f"{result['median_ms']:>9.2f} {result['p95_ms']:>9.2f} "
                f"{result['max_ms']:>9.2f}"
            )
        
        logger.info("="*120 + "\n")


def main():
    """Run benchmark suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark API endpoints")
    parser.add_argument("--output-dir", type=str, required=True, help="Directory for test data")
    parser.add_argument("--calls", type=int, default=30, help="Measured calls per endpoint (minimum 30)")
    parser.add_argument("--volume", choices=["small", "large"], default="small", help="Data volume size")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    runner = BenchmarkRunner(output_dir, args.volume)
    
    try:
        runner.run(args.calls)
        return 0
    except Exception as exc:
        logger.error(f"Benchmark failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
