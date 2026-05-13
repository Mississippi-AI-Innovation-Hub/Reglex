"""
OpenSearch index management for the v2 ingestion pipeline.

Creates and manages two indexes:
  - ms-phase1-legal: All MS boards (Phase 1)
  - multistate-phase2-legal: 3 boards x 7 states (Phase 2, future)

Each index stores two record types:
  - "document": full text per PDF, no embedding, for analytics
  - "page": per-page with embedding + structured fields, for retrieval
"""

from __future__ import annotations

from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from aws_session import AWSSession


# Index names
PHASE1_INDEX = "ms-phase1-legal"
PHASE2_INDEX = "multistate-phase2-legal"

# Shared mapping for both indexes
INDEX_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 512,
        },
        "analysis": {
            "analyzer": {
                "legal_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop"],
                }
            }
        },
    },
    "mappings": {
        "properties": {
            # ── Shared fields ──────────────────────────────
            "record_type": {"type": "keyword"},  # "document" or "page"
            "doc_id": {"type": "keyword"},
            "filename": {"type": "keyword"},
            "s3_key": {"type": "keyword"},
            "total_pages": {"type": "integer"},
            "ingested_at": {"type": "date"},

            # Phase 2 multi-state fields
            "state": {"type": "keyword"},
            "agency_type": {"type": "keyword"},
            "agency_name": {"type": "keyword"},

            # ── Document-level fields (record_type=document) ──
            "full_text": {"type": "text", "analyzer": "legal_analyzer"},
            "title": {"type": "text", "analyzer": "standard"},
            "board_or_agency": {"type": "text", "analyzer": "standard"},

            # ── Page-level fields (record_type=page) ─────────
            "page_id": {"type": "keyword"},
            "page_number": {"type": "integer"},
            "raw_text": {"type": "text", "analyzer": "legal_analyzer"},

            # Structured extraction
            "abstract_text": {"type": "text", "analyzer": "legal_analyzer"},
            "core_rule": {"type": "text", "analyzer": "legal_analyzer"},
            "statute_codes": {"type": "keyword"},
            "compliance_requirements": {"type": "text", "analyzer": "legal_analyzer"},
            "legal_entities": {"type": "keyword"},
            "section_identifier": {"type": "keyword"},
            "document_type": {"type": "keyword"},

            # Fees (nested for aggregation)
            "fee_amounts": {
                "type": "nested",
                "properties": {
                    "amount": {"type": "float"},
                    "fee_type": {"type": "keyword"},
                    "description": {"type": "text"},
                    "statutory_cap": {"type": "float"},
                },
            },

            # Dates
            "effective_date": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},
            "amendment_date": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},

            # Licensing
            "license_categories": {"type": "keyword"},
            "testing_requirements": {"type": "text", "analyzer": "legal_analyzer"},
            "statutory_authority_references": {"type": "keyword"},
            "reciprocity_provisions": {"type": "text", "analyzer": "legal_analyzer"},

            # Processing metadata
            "is_table_page": {"type": "boolean"},
            "used_vision": {"type": "boolean"},
            "extraction_model": {"type": "keyword"},

            # Titan text embedding (all page records)
            "text_embedding": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "faiss",
                    "parameters": {
                        "ef_construction": 512,
                        "m": 16,
                    },
                },
            },
        },
    },
}


class IndexManager:
    """Creates and manages OpenSearch indexes."""

    def __init__(self, session: AWSSession, endpoint: str):
        self.session = session
        self.endpoint = endpoint
        self._client = None  # type: OpenSearch

    def _get_client(self) -> OpenSearch:
        """Get or create OpenSearch client with current credentials."""
        if self._client is None:
            credentials = self.session._session.get_credentials().get_frozen_credentials()
            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                self.session.region,
                "es",
                session_token=credentials.token,
            )
            host = self.endpoint.replace("https://", "").replace("http://", "")
            self._client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=60,
            )
        return self._client

    def refresh_client(self):
        """Force refresh the OpenSearch client (after SSO re-login)."""
        self._client = None

    @property
    def client(self) -> OpenSearch:
        return self._get_client()

    def create_index(self, index_name: str) -> bool:
        """Create an index if it doesn't exist. Returns True if created."""
        if self.client.indices.exists(index=index_name):
            print(f"Index '{index_name}' already exists.")
            return False

        self.client.indices.create(index=index_name, body=INDEX_MAPPING)
        print(f"Created index: {index_name}")
        return True

    def delete_index(self, index_name: str) -> bool:
        """Delete an index. Returns True if deleted."""
        if not self.client.indices.exists(index=index_name):
            print(f"Index '{index_name}' does not exist.")
            return False

        self.client.indices.delete(index=index_name)
        print(f"Deleted index: {index_name}")
        return True

    def get_stats(self, index_name: str) -> dict:
        """Get document counts by record_type."""
        if not self.client.indices.exists(index=index_name):
            return {"exists": False}

        total = self.client.count(index=index_name)["count"]

        # Count by record_type
        agg_query = {
            "size": 0,
            "aggs": {
                "by_type": {
                    "terms": {"field": "record_type", "size": 10}
                },
                "unique_docs": {
                    "cardinality": {"field": "doc_id"}
                },
            },
        }
        resp = self.client.search(index=index_name, body=agg_query)
        aggs = resp.get("aggregations", {})

        type_counts = {
            b["key"]: b["doc_count"]
            for b in aggs.get("by_type", {}).get("buckets", [])
        }

        return {
            "exists": True,
            "total_records": total,
            "document_records": type_counts.get("document", 0),
            "page_records": type_counts.get("page", 0),
            "unique_documents": aggs.get("unique_docs", {}).get("value", 0),
        }

    def bulk_index(self, index_name: str, records: list[dict]) -> int:
        """
        Bulk index records into OpenSearch.
        Automatically chunks large payloads to stay under OpenSearch's 10MB limit.
        Returns the number of successfully indexed records.
        """
        if not records:
            return 0

        # OpenSearch has a 10MB request size limit. Batch in chunks of ~50 records
        # or split large docs. 50 records with embeddings ≈ 4-5MB.
        CHUNK_SIZE = 50
        total_ok = 0

        for i in range(0, len(records), CHUNK_SIZE):
            chunk = records[i:i + CHUNK_SIZE]
            total_ok += self._bulk_index_chunk(index_name, chunk)

        return total_ok

    def _bulk_index_chunk(self, index_name: str, records: list[dict]) -> int:
        """Index a single chunk of records (must be under 10MB)."""
        bulk_body = []
        for record in records:
            record_id = record.get("page_id") or record.get("doc_id")
            bulk_body.append({
                "index": {
                    "_index": index_name,
                    "_id": record_id,
                }
            })
            bulk_body.append(record)

        try:
            resp = self.client.bulk(body=bulk_body)
        except Exception as exc:
            # If a chunk is still too large, fall back to one-at-a-time
            if "413" in str(exc) or "size exceeded" in str(exc).lower():
                print(f"  Chunk too large, falling back to per-record indexing...")
                ok = 0
                for record in records:
                    try:
                        record_id = record.get("page_id") or record.get("doc_id")
                        self.client.index(index=index_name, id=record_id, body=record)
                        ok += 1
                    except Exception as e2:
                        print(f"    Record {record_id} failed: {e2}")
                return ok
            raise

        errors = sum(1 for item in resp["items"] if item["index"].get("error"))
        if errors:
            print(f"  Bulk index: {len(records) - errors}/{len(records)} succeeded, {errors} errors")
            for item in resp["items"]:
                if item["index"].get("error"):
                    print(f"    Error: {item['index']['error']}")

        return len(records) - errors
