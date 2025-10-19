"""Shared fixtures for taskweaver tests."""

import os

# Set dummy API key BEFORE any imports to prevent OpenAI client initialization errors
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")
