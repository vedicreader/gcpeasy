"""Shared test fixtures."""

import os
import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def auth():
    """A minimally-mocked GCPAuth without real ADC."""
    class _A:
        project = 'test-project'
        region = 'us-central1'
        credentials = MagicMock(name='credentials')
    return _A()


@pytest.fixture
def patched_env(monkeypatch):
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'test-project')
    monkeypatch.setenv('GOOGLE_CLOUD_REGION', 'us-central1')
    monkeypatch.setenv('GCPEASY_QUIET', '1')
    return monkeypatch
