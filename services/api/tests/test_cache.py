"""Unit tests for the in-process TTL cache."""

import threading
import unittest

from services.api.cache import InProcessTTLCache


class InProcessTTLCacheTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.cache = InProcessTTLCache(clock=lambda: self.now)

    def test_cache_hit_runs_loader_once(self):
        calls = []

        def loader():
            calls.append("load")
            return {"value": 1}

        self.assertEqual(self.cache.get_or_set("item", 60, loader), {"value": 1})
        self.assertEqual(self.cache.get_or_set("item", 60, loader), {"value": 1})
        self.assertEqual(calls, ["load"])

    def test_expired_entry_is_loaded_again(self):
        calls = []

        def loader():
            calls.append("load")
            return len(calls)

        self.assertEqual(self.cache.get_or_set("item", 60, loader), 1)
        self.now += 60
        self.assertEqual(self.cache.get_or_set("item", 60, loader), 2)

    def test_invalidate_key_and_prefix(self):
        self.cache.get_or_set("inventory.products", 60, lambda: "products")
        self.cache.get_or_set("inventory.orders", 60, lambda: "orders")
        self.cache.get_or_set("other", 60, lambda: "other")
        self.cache.invalidate("inventory.products")
        calls = []
        self.cache.get_or_set(
            "inventory.products",
            60,
            lambda: calls.append("products") or "new products",
        )
        self.cache.invalidate("inventory.", is_prefix=True)
        self.cache.get_or_set(
            "inventory.orders",
            60,
            lambda: calls.append("orders") or "new orders",
        )
        self.cache.get_or_set(
            "other",
            60,
            lambda: calls.append("other") or "new other",
        )
        self.assertEqual(calls, ["products", "orders"])

    def test_loader_exception_is_not_cached(self):
        calls = []

        def loader():
            calls.append("load")
            if len(calls) == 1:
                raise RuntimeError("database unavailable")
            return "loaded"

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            self.cache.get_or_set("item", 60, loader)
        self.assertEqual(self.cache.get_or_set("item", 60, loader), "loaded")
        self.assertEqual(self.cache.get_or_set("item", 60, loader), "loaded")
        self.assertEqual(calls, ["load", "load"])

    def test_invalidation_prevents_in_flight_loader_from_storing_stale_value(self):
        started = threading.Event()
        release = threading.Event()
        result = []

        def stale_loader():
            started.set()
            self.assertTrue(release.wait(timeout=2))
            return "stale"

        worker = threading.Thread(
            target=lambda: result.append(
                self.cache.get_or_set("item", 60, stale_loader)
            )
        )
        worker.start()
        self.assertTrue(started.wait(timeout=2))
        self.cache.invalidate("item")
        self.assertEqual(
            self.cache.get_or_set("item", 60, lambda: "fresh"),
            "fresh",
        )
        release.set()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, ["stale"])
        self.assertEqual(
            self.cache.get_or_set("item", 60, lambda: "unexpected"),
            "fresh",
        )


if __name__ == "__main__":
    unittest.main()
