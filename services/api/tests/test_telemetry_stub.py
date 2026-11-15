"""Tests for the Phase 1 telemetry stub."""

import json
import unittest

from fastapi.testclient import TestClient

from services.api.app import main


def make_event(event_type="page_viewed", **overrides):
    event = {
        "eventId": "7d1f6a52-3c0e-4b8a-9d2e-5f4c1a9b8e70",
        "timestamp": "2026-11-15T14:32:08.120Z",
        "sessionId": "0b9a3c4e-6d1f-4e2a-8c57-1f3e9a7b2d64",
        "userId": "42",
        "event_type": event_type,
        "schemaVersion": "1.0.0",
        "requestId": "none",
        "properties": {"route_template": "/inventory/products", "section": "inventory"},
    }
    event.update(overrides)
    return event


class TelemetryStubTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def post(self, payload):
        return self.client.post("/telemetry/events", json=payload)

    def test_valid_batch_returns_received_count(self):
        response = self.post({"events": [make_event(), make_event("login_failed")]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": 2})

    def test_accepts_text_plain_body_like_send_beacon(self):
        response = self.client.post(
            "/telemetry/events",
            content=json.dumps({"events": [make_event()]}),
            headers={"Content-Type": "text/plain;charset=UTF-8"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": 1})

    def test_accepts_anonymous_user_and_none_request_id(self):
        response = self.post({"events": [make_event(userId="anonymous", requestId="none")]})
        self.assertEqual(response.status_code, 200)

    def test_logs_count_and_event_types_without_properties(self):
        event = make_event("login_failed")
        event["properties"] = {"failure_reason": "secret-value-do-not-log"}
        with self.assertLogs("api.telemetry", level="INFO") as logs:
            self.post({"events": [make_event(), event]})
        output = "\n".join(logs.output)
        self.assertIn("count=2", output)
        self.assertIn("page_viewed", output)
        self.assertIn("login_failed", output)
        self.assertNotIn("secret-value-do-not-log", output)
        self.assertNotIn("42", output.replace("count=2", ""))

    def test_rejects_unknown_envelope_field(self):
        response = self.post({"events": [make_event(extra_field="x")]})
        self.assertEqual(response.status_code, 422)

    def test_rejects_wrong_event_type_format(self):
        response = self.post({"events": [make_event("PageViewed")]})
        self.assertEqual(response.status_code, 422)

    def test_rejects_empty_batch(self):
        self.assertEqual(self.post({"events": []}).status_code, 422)

    def test_rejects_invalid_json(self):
        response = self.client.post(
            "/telemetry/events",
            content="no es json",
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_email_as_user_id_without_echoing_it(self):
        response = self.post({"events": [make_event(userId="carla@example.com")]})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("carla@example.com", response.text)


if __name__ == "__main__":
    unittest.main()