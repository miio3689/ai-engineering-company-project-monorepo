"""Tests for the timing middleware logging."""

import logging
import unittest
from io import StringIO

from fastapi.testclient import TestClient

from services.api.app import main
from services.api.auth_security import get_current_user
from services.api.models import UserResponse, UserRole


class TimingMiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.user = UserResponse(
            id=1,
            email="test@example.com",
            is_active=True,
            role=UserRole.user,
            created_at="2026-01-01T00:00:00+00:00",
        )
        main.app.dependency_overrides[get_current_user] = lambda: self.user
        self.addCleanup(main.app.dependency_overrides.clear)
        
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
    
    def test_timing_middleware_logs_request_timing(self):
        """Verify timing middleware emits log with method, path, status, and duration."""
        # Capture logs
        timing_logger = logging.getLogger("api.timing")
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        
        original_handlers = timing_logger.handlers[:]
        timing_logger.handlers = [handler]
        
        try:
            # Make a request
            response = self.client.get("/auth/me")
            self.assertEqual(response.status_code, 200)
            
            # Check log was written
            log_output = log_capture.getvalue()
            self.assertIn("GET /auth/me 200", log_output)
            self.assertIn("ms", log_output)
        finally:
            timing_logger.handlers = original_handlers
    
    def test_timing_middleware_does_not_log_query_string(self):
        """Verify timing middleware logs path without query string."""
        timing_logger = logging.getLogger("api.timing")
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        
        original_handlers = timing_logger.handlers[:]
        timing_logger.handlers = [handler]
        
        try:
            # Make a request with query string
            response = self.client.get("/api/incidents?status=open&branch=central")
            self.assertEqual(response.status_code, 200)
            
            # Check log does NOT contain query string
            log_output = log_capture.getvalue()
            self.assertIn("GET /api/incidents 200", log_output)
            self.assertNotIn("status=open", log_output)
            self.assertNotIn("branch=central", log_output)
            self.assertNotIn("?", log_output)
        finally:
            timing_logger.handlers = original_handlers
    
    def test_timing_middleware_does_not_log_authorization_header(self):
        """Verify timing middleware does not log Authorization header."""
        timing_logger = logging.getLogger("api.timing")
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        
        original_handlers = timing_logger.handlers[:]
        timing_logger.handlers = [handler]
        
        try:
            # Make a request (which would have Authorization header)
            response = self.client.get("/auth/me")
            self.assertEqual(response.status_code, 200)
            
            # Check log does NOT contain Authorization
            log_output = log_capture.getvalue()
            self.assertNotIn("Authorization", log_output)
            self.assertNotIn("Bearer", log_output)
        finally:
            timing_logger.handlers = original_handlers
    
    def test_timing_middleware_does_not_log_request_body(self):
        """Verify timing middleware does not log request body."""
        timing_logger = logging.getLogger("api.timing")
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        
        original_handlers = timing_logger.handlers[:]
        timing_logger.handlers = [handler]
        
        try:
            # Make a POST request with body
            response = self.client.post(
                "/api/incidents",
                json={
                    "title": "Test incident",
                    "description": "Test description",
                    "category": "supply_issue",
                    "status": "open",
                    "origin": "customer",
                    "branch": "central",
                }
            )
            self.assertEqual(response.status_code, 201)
            
            # Check log does NOT contain body content
            log_output = log_capture.getvalue()
            self.assertIn("POST /api/incidents 201", log_output)
            self.assertNotIn("Test incident", log_output)
            self.assertNotIn("Test description", log_output)
        finally:
            timing_logger.handlers = original_handlers
    
    def test_timing_logs_different_status_codes(self):
        """Verify timing middleware logs correct status codes."""
        timing_logger = logging.getLogger("api.timing")
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        
        original_handlers = timing_logger.handlers[:]
        timing_logger.handlers = [handler]
        
        try:
            # 200 OK
            response = self.client.get("/auth/me")
            self.assertEqual(response.status_code, 200)
            
            # 404 Not Found
            response = self.client.get("/nonexistent")
            self.assertEqual(response.status_code, 404)
            
            log_output = log_capture.getvalue()
            lines = log_output.strip().split("\n")
            
            # Should have at least 2 lines
            self.assertGreaterEqual(len(lines), 2)
            self.assertIn("200", lines[-2])
            self.assertIn("404", lines[-1])
        finally:
            timing_logger.handlers = original_handlers


if __name__ == "__main__":
    unittest.main()
