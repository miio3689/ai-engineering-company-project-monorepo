"""Isolated API tests with an explicit, fake JWT signing key."""

import os

os.environ["JWT_SECRET_KEY"] = "fake-test-only-jwt-key-at-least-32-characters"
