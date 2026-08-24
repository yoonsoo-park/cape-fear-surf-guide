"""Durable, short-lived storage for public live MCP decisions.

The public MCP transport has no session or process affinity.  This module is
the only lookup boundary for a live ``window_id``: callers receive exactly the
stored decision payload, never a new source retrieval during explanation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


class RecordStore(Protocol):
    """Store serialized public decision payloads until their explicit expiry."""

    def put(self, window_id: str, payload: dict[str, Any], expires_at: int) -> None: ...

    def get(self, window_id: str) -> tuple[dict[str, Any] | None, int | None]: ...


class DynamoDbRecordStore:
    """A narrow DynamoDB adapter limited to one table's PutItem and GetItem."""

    def __init__(self, table_name: str, *, client: Any | None = None) -> None:
        if not table_name:
            raise ValueError("MCP_RECORD_TABLE must name the live-decision table")
        if client is None:
            import boto3

            client = boto3.client("dynamodb")
        self.table_name = table_name
        self.client = client

    def put(self, window_id: str, payload: dict[str, Any], expires_at: int) -> None:
        self.client.put_item(
            TableName=self.table_name,
            Item={
                "window_id": {"S": window_id},
                "expires_at": {"N": str(expires_at)},
                "payload": {"S": json.dumps(payload, sort_keys=True, separators=(",", ":"))},
            },
        )

    def get(self, window_id: str) -> tuple[dict[str, Any] | None, int | None]:
        response = self.client.get_item(
            TableName=self.table_name,
            Key={"window_id": {"S": window_id}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not isinstance(item, dict):
            return None, None
        try:
            return json.loads(item["payload"]["S"]), int(item["expires_at"]["N"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("Stored live decision is malformed") from error


@dataclass
class InMemoryRecordStore:
    """Test-only store.  It intentionally has no fallback-to-fixture behavior."""

    records: dict[str, tuple[dict[str, Any], int]] = field(default_factory=dict)

    def put(self, window_id: str, payload: dict[str, Any], expires_at: int) -> None:
        self.records[window_id] = (payload, expires_at)

    def get(self, window_id: str) -> tuple[dict[str, Any] | None, int | None]:
        return self.records.get(window_id, (None, None))


def unix_now() -> int:
    return int(time.time())
