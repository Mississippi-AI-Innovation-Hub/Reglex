"""
File-locked lease ledger for multi-session ingestion.

Multiple `pipeline.py` processes can run concurrently against the same index.
Each session claims a batch of S3 keys, processes them, and marks them done.
Other sessions read the ledger before claiming and skip taken keys.

Ledger structure (single JSON file, one per index):
    {
      "completed": ["s3/key1", "s3/key2", ...],
      "failed":    ["s3/keyN", ...],
      "leases": {
        "<session_id>": {
          "keys":         ["s3/k", ...],
          "claimed_at":   "2026-04-19T10:00:00Z",
          "heartbeat_at": "2026-04-19T10:02:30Z"
        }
      }
    }

Concurrency model: every read-modify-write acquires fcntl.LOCK_EX on the
ledger file. Stale leases (no heartbeat for STALE_LEASE_SECONDS) are auto-
released on the next claim/done by any session.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional


STALE_LEASE_SECONDS = 600  # 10 minutes without heartbeat → reclaimable


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def default_session_id() -> str:
    """Stable per-process session id: host-pid-shortuuid."""
    return "%s-%d-%s" % (socket.gethostname().split(".")[0], os.getpid(), uuid.uuid4().hex[:6])


def ledger_path(index_name: str, dirpath: Optional[str] = None) -> str:
    base = dirpath or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "ingestion_ledger_%s.json" % index_name)


class LeaseManager:
    """
    Coordinates S3-key claims across multiple local sessions via a single
    JSON ledger guarded by fcntl.flock.
    """

    def __init__(self, index_name: str, session_id: Optional[str] = None,
                 ledger_dir: Optional[str] = None):
        self.index_name = index_name
        self.session_id = session_id or default_session_id()
        self.path = ledger_path(index_name, ledger_dir)
        self._ensure_exists()

    # ── Internal: locked read-modify-write ──────────────────────────────

    def _ensure_exists(self):
        if not os.path.exists(self.path):
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump({"completed": [], "failed": [], "leases": {}}, f)

    @contextmanager
    def _locked(self):
        """Open the ledger with an exclusive lock, yield (data, fd), write+unlock on exit."""
        # Open r+ so we can both read and rewrite in place
        fd = open(self.path, "r+")
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            fd.seek(0)
            raw = fd.read()
            data = json.loads(raw) if raw.strip() else {"completed": [], "failed": [], "leases": {}}
            self._reap_stale(data)
            yield data
            # Write back
            fd.seek(0)
            fd.truncate()
            json.dump(data, fd, indent=2, default=str)
            fd.flush()
            os.fsync(fd.fileno())
        finally:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            fd.close()

    @staticmethod
    def _reap_stale(data: dict):
        """Remove leases whose heartbeat is older than STALE_LEASE_SECONDS."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_LEASE_SECONDS)
        stale = []
        for sid, lease in list(data.get("leases", {}).items()):
            try:
                last = _parse_iso(lease["heartbeat_at"])
            except Exception:
                stale.append(sid)
                continue
            if last < cutoff:
                stale.append(sid)
        for sid in stale:
            data["leases"].pop(sid, None)

    @staticmethod
    def _all_taken(data: dict) -> set:
        """Set of keys that are completed, failed, or actively leased by anyone."""
        taken = set(data.get("completed", []))
        taken.update(data.get("failed", []))
        for lease in data.get("leases", {}).values():
            taken.update(lease.get("keys", []))
        return taken

    # ── Public API ──────────────────────────────────────────────────────

    def claim_batch(self, candidate_keys: List[str], batch_size: int) -> List[str]:
        """
        Claim up to `batch_size` keys from `candidate_keys`, skipping any
        that are completed, failed, or held by another live session.

        Returns the list of keys claimed for this session (may be empty).
        """
        with self._locked() as data:
            taken = self._all_taken(data)
            mine = data["leases"].get(self.session_id, {}).get("keys", [])
            taken.update(mine)  # keep our own existing claim

            picked = []
            for k in candidate_keys:
                if k in taken:
                    continue
                picked.append(k)
                if len(picked) >= batch_size:
                    break

            if not picked and not mine:
                return []

            now = _now_iso()
            existing = data["leases"].get(self.session_id, {})
            data["leases"][self.session_id] = {
                "keys": list(set(mine + picked)),
                "claimed_at": existing.get("claimed_at", now),
                "heartbeat_at": now,
            }
            return picked

    def heartbeat(self):
        """Bump the heartbeat for our session. Cheap call — safe to do per-doc."""
        with self._locked() as data:
            lease = data["leases"].get(self.session_id)
            if lease:
                lease["heartbeat_at"] = _now_iso()

    def mark_done(self, key: str):
        """Move a key from our lease to the global completed set."""
        with self._locked() as data:
            if key not in data["completed"]:
                data["completed"].append(key)
            lease = data["leases"].get(self.session_id)
            if lease and key in lease.get("keys", []):
                lease["keys"].remove(key)
                lease["heartbeat_at"] = _now_iso()
            # Drop empty lease records
            if lease and not lease["keys"]:
                data["leases"].pop(self.session_id, None)

    def mark_failed(self, key: str):
        """Move a key from our lease to the global failed set."""
        with self._locked() as data:
            if key not in data["failed"]:
                data["failed"].append(key)
            lease = data["leases"].get(self.session_id)
            if lease and key in lease.get("keys", []):
                lease["keys"].remove(key)
                lease["heartbeat_at"] = _now_iso()
            if lease and not lease["keys"]:
                data["leases"].pop(self.session_id, None)

    def release(self):
        """Release any unfinished claims (call on clean shutdown)."""
        with self._locked() as data:
            data["leases"].pop(self.session_id, None)

    def stats(self) -> dict:
        """Snapshot of ledger state — for status printing."""
        with self._locked() as data:
            active = []
            for sid, lease in data.get("leases", {}).items():
                active.append({
                    "session": sid,
                    "in_flight": len(lease.get("keys", [])),
                    "heartbeat_at": lease.get("heartbeat_at"),
                })
            return {
                "completed": len(data.get("completed", [])),
                "failed": len(data.get("failed", [])),
                "active_sessions": active,
                "session_id": self.session_id,
            }

    def import_legacy_progress(self, completed_keys: List[str], failed_keys: List[str]):
        """One-shot: merge an old `ingestion_progress_*.json` into the new ledger."""
        with self._locked() as data:
            done = set(data.get("completed", []))
            done.update(completed_keys)
            data["completed"] = sorted(done)
            failed = set(data.get("failed", []))
            failed.update(failed_keys)
            data["failed"] = sorted(failed)
