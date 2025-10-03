"""Tests for cache module."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from zephy.cache import CacheEntry, save_to_cache, load_from_cache, get_cache_filename, cleanup_expired_cache


class TestCacheEntry:
    """Test CacheEntry class."""

    def test_init_with_timestamp(self):
        """Test initialization with custom timestamp."""
        data = {"test": "data"}
        ts = datetime(2023, 1, 1, 12, 0, 0)
        entry = CacheEntry(data, ts)
        assert entry.data == data
        assert entry.timestamp == ts

    def test_init_without_timestamp(self):
        """Test initialization with default timestamp."""
        data = {"test": "data"}
        entry = CacheEntry(data)
        assert entry.data == data
        assert isinstance(entry.timestamp, datetime)
        assert entry.timestamp <= datetime.now()

    def test_to_dict(self):
        """Test conversion to dictionary."""
        data = {"test": "data"}
        ts = datetime(2023, 1, 1, 12, 0, 0)
        entry = CacheEntry(data, ts)
        result = entry.to_dict()
        assert result["timestamp"] == "2023-01-01T12:00:00"
        assert result["data"] == data

    def test_make_serializable_primitives(self):
        """Test serialization of primitive types."""
        entry = CacheEntry(None)
        assert entry._make_serializable("string") == "string"
        assert entry._make_serializable(42) == 42
        assert entry._make_serializable(3.14) == 3.14
        assert entry._make_serializable(True) == True
        assert entry._make_serializable(None) is None

    def test_make_serializable_list(self):
        """Test serialization of lists."""
        entry = CacheEntry(None)
        data = [1, "string", {"key": "value"}]
        result = entry._make_serializable(data)
        assert result == [1, "string", {"key": "value"}]

    def test_make_serializable_dict(self):
        """Test serialization of dictionaries."""
        entry = CacheEntry(None)
        data = {"a": 1, "b": {"nested": "value"}}
        result = entry._make_serializable(data)
        assert result == {"a": 1, "b": {"nested": "value"}}

    def test_make_serializable_dataclass(self):
        """Test serialization of dataclass-like objects."""
        class MockObj:
            def __init__(self):
                self.attr1 = "value1"
                self.attr2 = 42
                self._private = "skip"

        entry = CacheEntry(None)
        obj = MockObj()
        result = entry._make_serializable(obj)
        assert result == {"attr1": "value1", "attr2": 42}
        assert "_private" not in result

    def test_make_serializable_unknown_type(self):
        """Test serialization of unknown types."""
        entry = CacheEntry(None)
        obj = object()
        result = entry._make_serializable(obj)
        assert isinstance(result, str)  # Should be string representation

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "timestamp": "2023-01-01T12:00:00",
            "data": {"test": "data"}
        }
        entry = CacheEntry.from_dict(data)
        assert entry.data == {"test": "data"}
        assert entry.timestamp == datetime(2023, 1, 1, 12, 0, 0)

    def test_is_fresh(self):
        """Test freshness checking."""
        ts = datetime.now() - timedelta(minutes=30)
        entry = CacheEntry("data", ts)

        assert entry.is_fresh(60)  # 30 min old, 60 min TTL
        assert not entry.is_fresh(20)  # 30 min old, 20 min TTL

    def test_is_fresh_future_timestamp(self):
        """Test freshness with future timestamp."""
        ts = datetime.now() + timedelta(minutes=10)
        entry = CacheEntry("data", ts)
        assert entry.is_fresh(5)  # Future timestamp should be fresh


class TestSaveLoadCache:
    """Test save_to_cache and load_from_cache functions."""

    def test_save_and_load_cache(self, tmp_path):
        """Test saving and loading cache."""
        cache_file = str(tmp_path / "test_cache.json")
        data = {"test": "data", "number": 42}

        # Save
        save_to_cache(data, cache_file, ttl_minutes=60)

        # Verify file exists
        assert Path(cache_file).exists()

        # Load
        loaded = load_from_cache(cache_file, ttl_minutes=60)
        assert loaded == data

    def test_load_nonexistent_cache(self, tmp_path):
        """Test loading non-existent cache file."""
        cache_file = str(tmp_path / "nonexistent.json")
        result = load_from_cache(cache_file)
        assert result is None

    def test_load_expired_cache(self, tmp_path):
        """Test loading expired cache."""
        cache_file = str(tmp_path / "expired_cache.json")
        data = {"test": "data"}

        # Save with past timestamp
        past_ts = datetime.now() - timedelta(minutes=120)
        entry = CacheEntry(data, past_ts)
        cache_data = {"ttl_minutes": 60, "entry": entry.to_dict()}

        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Load with short TTL
        loaded = load_from_cache(cache_file, ttl_minutes=60)
        assert loaded is None

    def test_load_corrupted_cache(self, tmp_path):
        """Test loading corrupted cache file."""
        cache_file = str(tmp_path / "corrupted.json")

        # Write invalid JSON
        with open(cache_file, "w") as f:
            f.write("invalid json")

        loaded = load_from_cache(cache_file)
        assert loaded is None

    def test_save_creates_directory(self, tmp_path):
        """Test save creates parent directories."""
        cache_dir = tmp_path / "cache" / "subdir"
        cache_file = str(cache_dir / "test.json")
        data = {"test": "data"}

        save_to_cache(data, cache_file)

        assert cache_dir.exists()
        assert Path(cache_file).exists()


class TestGetCacheFilename:
    """Test get_cache_filename function."""

    def test_get_cache_filename_basic(self):
        """Test basic filename generation."""
        result = get_cache_filename("azure_resources", "my-org", "sub-123", "primary")
        assert result == "azure_resources_my-org_sub-123_primary.json"

    def test_get_cache_filename_with_slashes(self):
        """Test filename generation with slashes in names."""
        result = get_cache_filename("tfe_resources", "org/name", "sub/id", "detailed")
        assert result == "tfe_resources_org_name_sub_id_detailed.json"

    def test_get_cache_filename_default_mode(self):
        """Test filename generation with default resource mode."""
        result = get_cache_filename("test", "org", "sub")
        assert result == "test_org_sub_primary.json"


class TestCleanupExpiredCache:
    """Test cleanup_expired_cache function."""

    def test_cleanup_expired_files(self, tmp_path):
        """Test cleanup removes expired files."""
        # Create expired cache file
        expired_file = tmp_path / "expired.json"
        past_ts = datetime.now() - timedelta(minutes=120)
        entry = CacheEntry("data", past_ts)
        cache_data = {"ttl_minutes": 60, "entry": entry.to_dict()}

        with open(expired_file, "w") as f:
            json.dump(cache_data, f)

        # Create fresh cache file
        fresh_file = tmp_path / "fresh.json"
        fresh_ts = datetime.now() - timedelta(minutes=30)
        entry = CacheEntry("data", fresh_ts)
        cache_data = {"ttl_minutes": 60, "entry": entry.to_dict()}

        with open(fresh_file, "w") as f:
            json.dump(cache_data, f)

        # Cleanup
        cleanup_expired_cache(str(tmp_path), ttl_minutes=60)

        # Expired file should be removed, fresh should remain
        assert not expired_file.exists()
        assert fresh_file.exists()

    def test_cleanup_corrupted_files(self, tmp_path):
        """Test cleanup removes corrupted files."""
        corrupted_file = tmp_path / "corrupted.json"

        # Write invalid JSON
        with open(corrupted_file, "w") as f:
            f.write("invalid json")

        cleanup_expired_cache(str(tmp_path))

        # Corrupted file should be removed
        assert not corrupted_file.exists()

    def test_cleanup_nonexistent_directory(self):
        """Test cleanup with non-existent directory."""
        # Should not raise error
        cleanup_expired_cache("/nonexistent/directory")