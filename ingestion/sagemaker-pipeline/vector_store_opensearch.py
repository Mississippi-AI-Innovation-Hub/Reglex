"""
OpenSearch Managed Vector Store for CLaRa Legal Analysis System.
Replaces ChromaDB with AWS-managed OpenSearch (Managed, not Serverless).

Uses hybrid search (kNN + BM25) with Reciprocal Rank Fusion for legal precision.
"""

import json
from typing import Optional, Callable
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from config import config
from models import CompressedAbstract, CompressedAbstractV2, FeeRecord, RetrievalResult


class OpenSearchVectorStore:
    """
    OpenSearch Managed-based vector store for compressed legal abstracts.
    
    Retrieval uses hybrid search: semantic vector similarity (kNN) combined
    with keyword matching (BM25), merged via Reciprocal Rank Fusion (RRF).
    This is essential for legal documents where exact statute references
    must be caught alongside semantic meaning.
    """
    
    # RRF constant — standard value from the original RRF paper.
    # Higher k reduces the influence of high rankings from a single method.
    RRF_K = 60
    
    def __init__(self):
        if not config.aws:
            raise ValueError("AWS configuration not set. Set USE_AWS=true in .env")
        
        self.config = config.aws
        self._init_opensearch_client()
        self._init_bedrock_embeddings()
    
    def _init_opensearch_client(self):
        """Initialize OpenSearch client with AWS authentication for Managed OpenSearch."""
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.config.region,
            'es',  # Service name for OpenSearch Managed (NOT 'aoss')
            session_token=credentials.token
        )
        
        host = self.config.opensearch_endpoint.replace('https://', '').replace('http://', '')
        
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=60
        )
    
    def _init_bedrock_embeddings(self):
        """Initialize Bedrock client for embeddings."""
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=self.config.region
        )
    
    def _create_index_if_not_exists(self):
        """Create OpenSearch index with vector field if it doesn't exist."""
        index_name = self.config.opensearch_index
        
        if self.client.indices.exists(index=index_name):
            return
        
        # Define index mapping for hybrid (k-NN + BM25) search
        # Phase 2: Added state, agency_type, agency_name, fee_amounts (nested),
        # effective_date, amendment_date, license_categories, testing_requirements,
        # statutory_authority_references, reciprocity_provisions
        index_body = {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 512
                }
            },
            "mappings": {
                "properties": {
                    "abstract_id": {"type": "keyword"},
                    "abstract_text": {"type": "text", "analyzer": "standard"},
                    "core_rule": {"type": "text", "analyzer": "standard"},
                    "source_document": {"type": "keyword"},
                    "source_path": {"type": "keyword"},
                    "page_numbers": {"type": "integer"},
                    "section_identifier": {"type": "keyword"},
                    "statute_codes": {"type": "keyword"},
                    "compliance_requirements": {"type": "text", "analyzer": "standard"},
                    "legal_entities": {"type": "keyword"},
                    "document_type": {"type": "keyword"},
                    "original_text": {"type": "text", "analyzer": "standard"},
                    "compression_model": {"type": "keyword"},
                    # Phase 2: multi-state fields
                    "state": {"type": "keyword"},
                    "agency_type": {"type": "keyword"},
                    "agency_name": {"type": "keyword"},
                    "fee_amounts": {
                        "type": "nested",
                        "properties": {
                            "amount": {"type": "float"},
                            "fee_type": {"type": "keyword"},
                            "description": {"type": "text"},
                            "statutory_cap": {"type": "float"},
                        }
                    },
                    "effective_date": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},
                    "amendment_date": {"type": "date", "format": "yyyy-MM-dd||epoch_millis"},
                    "license_categories": {"type": "keyword"},
                    "testing_requirements": {"type": "text", "analyzer": "standard"},
                    "statutory_authority_references": {"type": "keyword"},
                    "reciprocity_provisions": {"type": "text", "analyzer": "standard"},
                    "embedding_vector": {
                        "type": "knn_vector",
                        "dimension": 1024,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "faiss",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16
                            }
                        }
                    }
                }
            }
        }
        
        self.client.indices.create(index=index_name, body=index_body)
        print(f"Created index: {index_name}")
    
    def _get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding using Amazon Titan Embed Text v2.
        
        Titan v2 produces 1024-dim normalized vectors suitable for cosine similarity.
        """
        body = json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
        
        response = self.bedrock.invoke_model(
            modelId=self.config.bedrock_embedding_model,
            body=body,
            contentType='application/json',
            accept='application/json'
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['embedding']
    
    def _create_embedding_text(self, abstract: CompressedAbstract) -> str:
        """
        Create rich embedding text from both the structured abstract AND original source.
        
        The original legal text is included so the vector captures actual legal language,
        not just the LLM's potentially lossy summary. This prevents silent retrieval
        failures where the compression mischaracterized a provision.
        """
        parts = [
            abstract.abstract_text,
            f"Core rule: {abstract.core_rule}",
        ]
        
        if abstract.statute_codes:
            parts.append(f"Statutes: {', '.join(abstract.statute_codes)}")
        
        if abstract.compliance_requirements:
            parts.append(f"Requirements: {'; '.join(abstract.compliance_requirements)}")
        
        if abstract.section_identifier:
            parts.append(f"Section: {abstract.section_identifier}")
        
        # Include original text so the vector represents actual legal language,
        # not just the LLM's interpretation. Truncate to prevent diluting the
        # semantic signal — Cohere v4 handles long inputs but focus matters.
        if abstract.original_text:
            parts.append(f"Source text: {abstract.original_text[:1500]}")
        
        return " | ".join(parts)
    
    def _build_doc(self, abstract: CompressedAbstract, embedding: list[float]) -> dict:
        """Build the OpenSearch document body from an abstract + embedding."""
        doc = {
            "abstract_id": abstract.abstract_id,
            "abstract_text": abstract.abstract_text,
            "core_rule": abstract.core_rule,
            "source_document": abstract.source_document,
            "source_path": abstract.source_path,
            "page_numbers": abstract.page_numbers,
            "section_identifier": abstract.section_identifier,
            "statute_codes": abstract.statute_codes,
            "compliance_requirements": abstract.compliance_requirements,
            "legal_entities": abstract.legal_entities,
            "document_type": abstract.document_type,
            "original_text": abstract.original_text[:5000],
            "compression_model": abstract.compression_model,
            "embedding_vector": embedding,
        }
        # Phase 2: include V2 fields if present
        if isinstance(abstract, CompressedAbstractV2):
            doc.update({
                "state": abstract.state,
                "agency_type": abstract.agency_type,
                "agency_name": abstract.agency_name,
                "fee_amounts": [f.model_dump() for f in abstract.fee_amounts],
                "effective_date": abstract.effective_date.isoformat() if abstract.effective_date else None,
                "amendment_date": abstract.amendment_date.isoformat() if abstract.amendment_date else None,
                "license_categories": abstract.license_categories,
                "testing_requirements": abstract.testing_requirements,
                "statutory_authority_references": abstract.statutory_authority_references,
                "reciprocity_provisions": abstract.reciprocity_provisions,
            })
        return doc

    def add_abstract(self, abstract: CompressedAbstract):
        """Add a single compressed abstract to OpenSearch."""
        self._create_index_if_not_exists()

        embedding_text = self._create_embedding_text(abstract)
        embedding = self._get_embedding(embedding_text)
        doc = self._build_doc(abstract, embedding)

        self.client.index(
            index=self.config.opensearch_index,
            id=abstract.abstract_id,
            body=doc
        )
    
    def add_abstracts(
        self,
        abstracts: list[CompressedAbstract],
        batch_size: int = 50,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ):
        """Add multiple abstracts using bulk indexing."""
        self._create_index_if_not_exists()

        total = len(abstracts)

        for i in range(0, total, batch_size):
            batch = abstracts[i:i + batch_size]

            bulk_body = []
            for abstract in batch:
                embedding_text = self._create_embedding_text(abstract)
                embedding = self._get_embedding(embedding_text)

                bulk_body.append({
                    "index": {
                        "_index": self.config.opensearch_index,
                        "_id": abstract.abstract_id
                    }
                })
                bulk_body.append(self._build_doc(abstract, embedding))

            self.client.bulk(body=bulk_body)

            if progress_callback:
                progress_callback(min(i + batch_size, total), total)
    
    # ──────────────────────────────────────────────────────────────────────
    # HYBRID SEARCH: kNN (semantic) + BM25 (keyword) merged via RRF
    # ──────────────────────────────────────────────────────────────────────
    
    @staticmethod
    def _build_filters(
        filter_document: Optional[str] = None,
        filter_state: Optional[str] = None,
        filter_agency_type: Optional[str] = None,
        filter_states: Optional[list[str]] = None,
    ) -> list[dict]:
        """Build a list of OpenSearch filter clauses from optional parameters."""
        filters = []
        if filter_document:
            filters.append({"term": {"source_document": filter_document}})
        if filter_state:
            filters.append({"term": {"state.keyword": filter_state}})
        if filter_agency_type:
            filters.append({"term": {"agency_type.keyword": filter_agency_type}})
        if filter_states:
            filters.append({"terms": {"state.keyword": filter_states}})
        return filters

    def _knn_search(
        self,
        query_embedding: list[float],
        top_k: int,
        filter_document: Optional[str] = None,
        filter_state: Optional[str] = None,
        filter_agency_type: Optional[str] = None,
        filter_states: Optional[list[str]] = None,
    ) -> list[dict]:
        """Semantic vector similarity search via kNN."""
        knn_query: dict = {
            "size": top_k,
            "query": {
                "knn": {
                    "embedding_vector": {
                        "vector": query_embedding,
                        "k": top_k
                    }
                }
            }
        }

        filters = self._build_filters(filter_document, filter_state, filter_agency_type, filter_states)
        if filters:
            knn_query["query"] = {
                "bool": {
                    "must": [knn_query["query"]],
                    "filter": filters
                }
            }

        response = self.client.search(
            index=self.config.opensearch_index,
            body=knn_query
        )
        return response['hits']['hits']
    
    def _bm25_search(
        self,
        query: str,
        top_k: int,
        filter_document: Optional[str] = None,
        filter_state: Optional[str] = None,
        filter_agency_type: Optional[str] = None,
        filter_states: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        BM25 keyword search across legal text fields.

        Boost factors are calibrated for legal document retrieval:
        - statute_codes (4x): exact legal references like "§ 75-1-101" are unambiguous
        - section_identifier (3x): section headers are high-signal
        - abstract_text / core_rule (2x): distilled legal meaning
        - original_text (1.5x): ground truth but noisy
        - legal_entities (1x): agencies, offices
        - Phase 2: statutory_authority_references (3.5x), testing_requirements (1.5x),
          reciprocity_provisions (1.5x)
        """
        bm25_query: dict = {
            "size": top_k,
            "query": {
                "bool": {
                    "should": [
                        {"match": {"statute_codes": {"query": query, "boost": 4.0}}},
                        {"match": {"statutory_authority_references": {"query": query, "boost": 3.5}}},
                        {"match": {"section_identifier": {"query": query, "boost": 3.0}}},
                        {"match": {"abstract_text": {"query": query, "boost": 2.0}}},
                        {"match": {"core_rule": {"query": query, "boost": 2.0}}},
                        {"match": {"original_text": {"query": query, "boost": 1.5}}},
                        {"match": {"compliance_requirements": {"query": query, "boost": 1.5}}},
                        {"match": {"testing_requirements": {"query": query, "boost": 1.5}}},
                        {"match": {"reciprocity_provisions": {"query": query, "boost": 1.5}}},
                        {"match": {"legal_entities": {"query": query, "boost": 1.0}}},
                    ],
                    "minimum_should_match": 1
                }
            }
        }

        filters = self._build_filters(filter_document, filter_state, filter_agency_type, filter_states)
        if filters:
            bm25_query["query"]["bool"]["filter"] = filters

        response = self.client.search(
            index=self.config.opensearch_index,
            body=bm25_query
        )
        return response['hits']['hits']
    
    @staticmethod
    def _rrf_merge(
        knn_hits: list[dict],
        bm25_hits: list[dict],
        top_k: int,
        rrf_k: int = 60
    ) -> list[dict]:
        """
        Merge kNN and BM25 results using Reciprocal Rank Fusion.
        
        RRF score(d) = Σ 1/(k + rank_i(d)) across each ranking method.
        This normalizes the incompatible score scales (cosine similarity
        vs BM25 tf-idf) without requiring score calibration.
        
        Reference: Cormack, Clarke, Butt (2009) — "Reciprocal Rank Fusion 
        outperforms Condorcet and individual Rank Learning Methods"
        """
        scores: dict[str, dict] = {}
        
        # Accumulate kNN ranks
        for rank, hit in enumerate(knn_hits):
            doc_id = hit['_id']
            scores[doc_id] = {
                'rrf_score': 1.0 / (rrf_k + rank + 1),
                'source': hit['_source'],
            }
        
        # Accumulate BM25 ranks (additive with kNN)
        for rank, hit in enumerate(bm25_hits):
            doc_id = hit['_id']
            rrf_increment = 1.0 / (rrf_k + rank + 1)
            
            if doc_id in scores:
                # Document found by BOTH methods — strongest signal
                scores[doc_id]['rrf_score'] += rrf_increment
            else:
                scores[doc_id] = {
                    'rrf_score': rrf_increment,
                    'source': hit['_source'],
                }
        
        # Sort by fused score descending, take top_k
        ranked = sorted(scores.items(), key=lambda x: x[1]['rrf_score'], reverse=True)
        return [
            {'_id': doc_id, '_source': data['source'], '_score': data['rrf_score']}
            for doc_id, data in ranked[:top_k]
        ]
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_document: Optional[str] = None,
        filter_state: Optional[str] = None,
        filter_agency_type: Optional[str] = None,
        filter_states: Optional[list[str]] = None,
    ) -> list[RetrievalResult]:
        """
        Hybrid search combining vector similarity (kNN) and keyword matching (BM25).

        Uses Reciprocal Rank Fusion to merge results from both methods.
        Critical for legal documents where:
        - Exact statute references (e.g., "§ 75-1-101") need keyword matching
        - Conceptual questions (e.g., "notary renewal requirements") need semantic search
        - Both methods together catch what either alone would miss

        Phase 2: Now supports filtering by state, agency_type, and multi-state lists.
        """
        top_k = top_k or config.retrieval.top_k

        # Fetch a wider candidate pool from each method, then fuse to top_k.
        candidate_pool = top_k * 3

        # Phase 1: Semantic vector search
        query_embedding = self._get_embedding(query)
        knn_hits = self._knn_search(
            query_embedding, candidate_pool,
            filter_document=filter_document,
            filter_state=filter_state,
            filter_agency_type=filter_agency_type,
            filter_states=filter_states,
        )

        # Phase 2: BM25 keyword search
        bm25_hits = self._bm25_search(
            query, candidate_pool,
            filter_document=filter_document,
            filter_state=filter_state,
            filter_agency_type=filter_agency_type,
            filter_states=filter_states,
        )

        # Phase 3: Reciprocal Rank Fusion
        merged_hits = self._rrf_merge(knn_hits, bm25_hits, top_k, rrf_k=self.RRF_K)

        # Convert to RetrievalResult objects
        results = []
        for i, hit in enumerate(merged_hits):
            source = hit['_source']
            rrf_score = hit['_score']

            # Hydrate V2 fields if present, otherwise fall back to V1
            has_v2 = "state" in source and source.get("state")
            if has_v2:
                fee_records = [
                    FeeRecord(**f) for f in source.get("fee_amounts", [])
                ] if source.get("fee_amounts") else []

                abstract = CompressedAbstractV2(
                    abstract_id=source['abstract_id'],
                    source_document=source['source_document'],
                    source_path=source.get('source_path', ''),
                    page_numbers=source['page_numbers'],
                    section_identifier=source.get('section_identifier'),
                    abstract_text=source['abstract_text'],
                    core_rule=source.get('core_rule'),
                    statute_codes=source.get('statute_codes', []),
                    compliance_requirements=source.get('compliance_requirements', []),
                    legal_entities=source.get('legal_entities', []),
                    original_text=source.get('original_text', ''),
                    document_type=source.get('document_type', 'unknown'),
                    compression_model=source.get('compression_model', ''),
                    state=source.get('state', 'MS'),
                    agency_type=source.get('agency_type', ''),
                    agency_name=source.get('agency_name', ''),
                    fee_amounts=fee_records,
                    effective_date=source.get('effective_date'),
                    amendment_date=source.get('amendment_date'),
                    license_categories=source.get('license_categories', []),
                    testing_requirements=source.get('testing_requirements'),
                    statutory_authority_references=source.get('statutory_authority_references', []),
                    reciprocity_provisions=source.get('reciprocity_provisions'),
                )
            else:
                abstract = CompressedAbstract(
                    abstract_id=source['abstract_id'],
                    source_document=source['source_document'],
                    source_path=source.get('source_path', ''),
                    page_numbers=source['page_numbers'],
                    section_identifier=source.get('section_identifier'),
                    abstract_text=source['abstract_text'],
                    core_rule=source.get('core_rule'),
                    statute_codes=source.get('statute_codes', []),
                    compliance_requirements=source.get('compliance_requirements', []),
                    legal_entities=source.get('legal_entities', []),
                    original_text=source.get('original_text', ''),
                    document_type=source.get('document_type', 'unknown'),
                    compression_model=source.get('compression_model', ''),
                )

            results.append(RetrievalResult(
                abstract=abstract,
                similarity_score=rrf_score,
                rank=i + 1
            ))

        return results

    # ──────────────────────────────────────────────────────────────────────
    # AGGREGATION QUERIES (Phase 2)
    # ──────────────────────────────────────────────────────────────────────

    def aggregate_fees(
        self,
        filter_state: Optional[str] = None,
        filter_agency_type: Optional[str] = None,
        filter_states: Optional[list[str]] = None,
    ) -> dict:
        """
        Aggregate fee information across documents.

        Returns fee stats grouped by state and fee_type using nested aggregations.
        """
        query: dict = {"size": 0, "query": {"match_all": {}}}

        filters = self._build_filters(
            filter_state=filter_state,
            filter_agency_type=filter_agency_type,
            filter_states=filter_states,
        )
        if filters:
            query["query"] = {"bool": {"filter": filters}}

        query["aggs"] = {
            "by_state": {
                "terms": {"field": "state", "size": 10},
                "aggs": {
                    "fees": {
                        "nested": {"path": "fee_amounts"},
                        "aggs": {
                            "by_type": {
                                "terms": {"field": "fee_amounts.fee_type", "size": 20},
                                "aggs": {
                                    "avg_amount": {"avg": {"field": "fee_amounts.amount"}},
                                    "max_amount": {"max": {"field": "fee_amounts.amount"}},
                                    "min_amount": {"min": {"field": "fee_amounts.amount"}},
                                }
                            }
                        }
                    }
                }
            }
        }

        response = self.client.search(index=self.config.opensearch_index, body=query)
        return response.get("aggregations", {})
    
    def get_stats(self) -> dict:
        """Get statistics about the vector store."""
        index_name = self.config.opensearch_index
        
        if not self.client.indices.exists(index=index_name):
            return {
                "total_abstracts": 0,
                "unique_documents": 0,
                "documents": [],
                "index_name": index_name
            }
        
        count = self.client.count(index=index_name)['count']
        
        agg_query = {
            "size": 0,
            "aggs": {
                "unique_documents": {
                    "terms": {
                        "field": "source_document",
                        "size": 10000
                    }
                }
            }
        }
        
        response = self.client.search(index=index_name, body=agg_query)
        documents = [bucket['key'] for bucket in response['aggregations']['unique_documents']['buckets']]
        
        return {
            "total_abstracts": count,
            "unique_documents": len(documents),
            "documents": documents,
            "index_name": index_name
        }
    
    def clear(self):
        """Delete and recreate the index."""
        index_name = self.config.opensearch_index
        
        if self.client.indices.exists(index=index_name):
            self.client.indices.delete(index=index_name)
        
        self._create_index_if_not_exists()
    
    def delete_document(self, document_name: str):
        """Delete all abstracts from a specific document."""
        query = {
            "query": {
                "term": {"source_document": document_name}
            }
        }
        
        response = self.client.search(
            index=self.config.opensearch_index,
            body=query,
            _source=False
        )
        
        if response['hits']['hits']:
            ids = [hit['_id'] for hit in response['hits']['hits']]
            
            for doc_id in ids:
                self.client.delete(
                    index=self.config.opensearch_index,
                    id=doc_id
                )
