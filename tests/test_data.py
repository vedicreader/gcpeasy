"""Tests for `data` (signed_url validation, create_collection no-op, GCS uniform)."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def test_signed_url_rejects_too_long_expiry(auth):
    from gcpeasy.data import signed_url
    with pytest.raises(ValueError, match='168'):
        signed_url(auth, 'b', 'k', hours=200)


def test_signed_url_rejects_zero_or_negative(auth):
    from gcpeasy.data import signed_url
    with pytest.raises(ValueError, match='> 0'):
        signed_url(auth, 'b', 'k', hours=0)
    with pytest.raises(ValueError):
        signed_url(auth, 'b', 'k', hours=-1)


def test_create_collection_is_pure_metadata(auth):
    """Regression: must NOT write a placeholder doc into Firestore."""
    from gcpeasy.data import create_collection

    fake_module = MagicMock()
    fake_client = MagicMock()
    fake_module.Client.return_value = fake_client

    # Even if firestore is mocked, the function should not touch it.
    with patch('gcpeasy.data.fs', fake_module, create=True):
        out = create_collection(auth, 'sessions')

    assert out == 'sessions'
    fake_module.Client.assert_not_called()
    fake_client.collection.assert_not_called()


def test_create_bucket_sets_uniform_access_at_creation(auth):
    """Regression: uniform_bucket_level_access should be set on the local Bucket
    object before create_bucket(), not patched in afterward."""
    from gcpeasy.data import create_bucket

    fake_storage = MagicMock()
    fake_client = MagicMock()
    fake_storage.Client.return_value = fake_client
    # Simulate "bucket does not exist"
    fake_client.get_bucket.side_effect = Exception('nf')
    bucket_local = MagicMock()
    iam_cfg = MagicMock()
    bucket_local.iam_configuration = iam_cfg
    fake_client.bucket.return_value = bucket_local
    bucket_created = MagicMock()
    bucket_created.name = 'b'
    bucket_created.location = 'us-central1'
    fake_client.create_bucket.return_value = bucket_created

    with patch('gcpeasy.data.storage', fake_storage, create=True):
        create_bucket(auth, 'b')

    # The setter on the *local* Bucket object should have been called BEFORE
    # create_bucket(). We simply verify it was assigned True.
    assert iam_cfg.uniform_bucket_level_access_enabled is True
    fake_client.create_bucket.assert_called_once()
