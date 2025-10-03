"""File system caching utilities."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from . import logger


class CacheEntry:
    """Cache entry with timestamp and data."""

    def __init__(self, data: Any, timestamp: Optional[datetime] = None):
        """Initialize cache entry.

        Args:
            data: Data to cache
            timestamp: Timestamp when data was cached (defaults to now)
        """
        self.data = data
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        # Convert dataclass objects to dictionaries if needed
        serializable_data = self._make_serializable(self.data)
        return {
            "timestamp": self.timestamp.isoformat(),
            "data": serializable_data}

    def _make_serializable(self, obj: Any) -> Any:
        """Convert non-serializable objects to serializable format."""
        if isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._make_serializable(
                value) for key, value in obj.items()}
        elif hasattr(obj, "__dict__"):
            # Convert dataclass or other objects with __dict__ to dict
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith("_"):  # Skip private attributes
                    result[key] = self._make_serializable(value)
            return result
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # For other types, convert to string representation
            return str(obj)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(data["data"], timestamp)

    def is_fresh(self, ttl_minutes: int) -> bool:
        """Check if cache entry is still fresh.

        Args:
            ttl_minutes: Time-to-live in minutes

        Returns:
            True if entry is within TTL
        """
        expiry = self.timestamp + timedelta(minutes=ttl_minutes)
        return datetime.now() < expiry


def save_to_cache(data: Any, cache_file: str, ttl_minutes: int = 60) -> None:
    """Save data to cache file with timestamp.

    Args:
        data: Data to cache
        cache_file: Path to cache file
        ttl_minutes: Time-to-live in minutes (for metadata)
    """
    cache_path = Path(cache_file)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    entry = CacheEntry(data)
    cache_data = {"ttl_minutes": ttl_minutes, "entry": entry.to_dict()}

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        logger.get_logger(__name__).debug(f"Saved cache to: {cache_file}")
    except Exception as e:
        logger.get_logger(__name__).warning(
            f"Failed to save cache to {cache_file}: {e}"
        )


def load_from_cache(cache_file: str, ttl_minutes: int = 60) -> Optional[Any]:
    """Load data from cache file if it exists and is fresh.

    Args:
        cache_file: Path to cache file
        ttl_minutes: Time-to-live in minutes

    Returns:
        Cached data if fresh, None otherwise
    """
    cache_path = Path(cache_file)
    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        entry_dict = cache_data.get("entry", {})
        entry = CacheEntry.from_dict(entry_dict)

        if entry.is_fresh(ttl_minutes):
            logger.get_logger(__name__).debug(
                f"Loaded fresh cache from: {cache_file}")
            return entry.data
        else:
            logger.get_logger(__name__).debug(
                f"Cache expired for: {cache_file}")
            return None

    except Exception as e:
        logger.get_logger(__name__).warning(
            f"Failed to load cache from {cache_file}: {e}"
        )
        return None


def get_cache_filename(
    base_name: str, org: str, subscription: str, resource_mode: str = "primary"
) -> str:
    """Generate cache filename based on parameters.

    Args:
        base_name: Base name (e.g., 'azure_resources', 'tfe_resources')
        org: TFE organization name
        subscription: Azure subscription ID
        resource_mode: Resource filtering mode

    Returns:
        Cache filename
    """
    # Sanitize names for filename
    safe_org = org.replace("/", "_").replace("\\", "_")
    safe_sub = subscription.replace("/", "_").replace("\\", "_")

    return f"{base_name}_{safe_org}_{safe_sub}_{resource_mode}.json"


def cleanup_expired_cache(cache_dir: str = ".", ttl_minutes: int = 60) -> None:
    """Remove expired cache files from directory.

    Args:
        cache_dir: Directory to clean up
        ttl_minutes: Time-to-live in minutes
    """
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return

    log = logger.get_logger(__name__)
    removed_count = 0

    for cache_file in cache_path.glob("*.json"):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            entry_dict = cache_data.get("entry", {})
            entry = CacheEntry.from_dict(entry_dict)

            if not entry.is_fresh(ttl_minutes):
                cache_file.unlink()
                removed_count += 1

        except Exception:
            # If we can't read the file, it's probably corrupted, remove it
            try:
                cache_file.unlink()
                removed_count += 1
            except Exception:
                pass

    if removed_count > 0:
        log.debug(f"Cleaned up {removed_count} expired cache files")
