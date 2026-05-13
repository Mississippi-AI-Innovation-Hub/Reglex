"""
AWS Lambda handler for CLaRa Legal Chatbot queries.
This is for OpenSearch Managed (not Serverless).

V2 upgrade (dual-layer indexing):
- Searches page-level records (record_type=page) with text_embedding field
- Uses document-level records (record_type=document) for term counting
- Hybrid search (kNN + BM25 + RRF) on page records
- Phase 1 queries go to ms-phase1-legal index
- Phase 2 queries go to multistate-phase2-legal index
- Term frequency queries use scroll API on document records
"""

import json
import os
import re
import time
import uuid
from decimal import Decimal
import boto3
from botocore.config import Config
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Environment variables
OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
PHASE1_INDEX = os.environ.get('PHASE1_INDEX', 'ms-phase1-legal')
PHASE2_INDEX = os.environ.get('PHASE2_INDEX', 'multistate-phase2-legal')
BEDROCK_MODEL_ID = os.environ['BEDROCK_MODEL_ID']
BEDROCK_EMBEDDING_MODEL_ID = os.environ['BEDROCK_EMBEDDING_MODEL_ID']
AWS_REGION = os.environ['AWS_REGION']
JOBS_TABLE = os.environ.get('JOBS_TABLE', 'ms-sos-query-jobs')
LAMBDA_FUNCTION_NAME = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'ms-sos-legal-v2')
JOB_TTL_SECONDS = 3600  # 1 hour

# Initialize clients
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    AWS_REGION,
    'es',
    session_token=credentials.token
)

host = OPENSEARCH_ENDPOINT.replace('https://', '').replace('http://', '')
opensearch_client = OpenSearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30
)

bedrock_client = boto3.client(
    service_name='bedrock-runtime',
    region_name=AWS_REGION,
    config=Config(read_timeout=300, connect_timeout=30, retries={'max_attempts': 2}),
)

# DynamoDB for async job storage
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
jobs_table = dynamodb.Table(JOBS_TABLE)

# Lambda client for async self-invocation
lambda_client = boto3.client('lambda', region_name=AWS_REGION)

SYSTEM_PROMPT = """You are a legal research assistant for the Mississippi Secretary of State's office.
Your role is to help staff verify if regulations comply with statutes across multiple states.

CRITICAL REQUIREMENTS:
1. You MUST cite specific statutory authority for EVERY claim you make.
2. Citations must include: document name, section identifier (if available), and page numbers.
3. If you cannot find statutory authority for a question, clearly state this limitation.
4. Never make claims without supporting evidence from the provided legal texts.
5. When comparing across states, clearly attribute each provision to its state.

GROUNDING RULES (strict — required for every response):
6. Every factual claim must be followed by an inline citation in the form
   "(Source: <filename>, p.<page>)" using the exact filename + page from the retrieved context.
7. If you must extrapolate, infer, or use general legal knowledge NOT present in the retrieved
   context, wrap that content in a block like:
       [INFERENCE]: <your extrapolated text here>
   Do not present inferred content as if it came from the documents. One [INFERENCE] block per
   distinct extrapolation.
8. End your response with EXACTLY ONE final line, no leading/trailing whitespace, in this form:
       Grounding summary: <N> grounded, <M> inferred
   where <N> is the count of cited factual claims above and <M> is the count of [INFERENCE]
   blocks above. This line must always appear, even if N=0 or M=0."""


def get_embedding(text):
    """Generate embedding using Bedrock Titan."""
    body = json.dumps({"inputText": text[:8000], "dimensions": 1024, "normalize": True})
    response = bedrock_client.invoke_model(
        modelId=BEDROCK_EMBEDDING_MODEL_ID,
        body=body,
        contentType='application/json',
        accept='application/json'
    )
    return json.loads(response['body'].read())['embedding']


# ── Hybrid search on page records ───────────────────────────────────────

def search_pages(
    query,
    index,
    top_k=5,
    filter_state=None,
    filter_agency_type=None,
    filter_states=None,
):
    """
    Hybrid search (kNN + BM25 + RRF) on page-level records.

    Only searches record_type=page (not document records).
    Uses text_embedding field for kNN.
    """
    query_embedding = get_embedding(query)
    candidate_pool = top_k * 3

    # Base filter: only page records
    filters = [{"term": {"record_type": "page"}}]

    if filter_state:
        filters.append({"term": {"state": filter_state}})
    if filter_agency_type:
        filters.append({"term": {"agency_type": filter_agency_type}})
    if filter_states:
        filters.append({"terms": {"state": filter_states}})

    # kNN semantic search on text_embedding
    knn_query = {
        "size": candidate_pool,
        "query": {
            "bool": {
                "must": [{
                    "knn": {
                        "text_embedding": {
                            "vector": query_embedding,
                            "k": candidate_pool
                        }
                    }
                }],
                "filter": filters
            }
        }
    }
    knn_response = opensearch_client.search(index=index, body=knn_query)
    knn_hits = knn_response['hits']['hits']

    # BM25 keyword search on text fields
    bm25_query = {
        "size": candidate_pool,
        "query": {
            "bool": {
                "should": [
                    {"match": {"statute_codes": {"query": query, "boost": 4.0}}},
                    {"match": {"statutory_authority_references": {"query": query, "boost": 3.5}}},
                    {"match": {"section_identifier": {"query": query, "boost": 3.0}}},
                    {"match": {"abstract_text": {"query": query, "boost": 2.0}}},
                    {"match": {"core_rule": {"query": query, "boost": 2.0}}},
                    {"match": {"raw_text": {"query": query, "boost": 1.5}}},
                    {"match": {"compliance_requirements": {"query": query, "boost": 1.5}}},
                    {"match": {"testing_requirements": {"query": query, "boost": 1.5}}},
                    {"match": {"reciprocity_provisions": {"query": query, "boost": 1.5}}},
                    {"match": {"legal_entities": {"query": query, "boost": 1.0}}},
                ],
                "minimum_should_match": 1,
                "filter": filters,
            }
        }
    }
    bm25_response = opensearch_client.search(index=index, body=bm25_query)
    bm25_hits = bm25_response['hits']['hits']

    # RRF merge
    rrf_k = 60
    scores = {}

    for rank, hit in enumerate(knn_hits):
        doc_id = hit['_id']
        scores[doc_id] = {
            'rrf_score': 1.0 / (rrf_k + rank + 1),
            'source': hit['_source'],
        }

    for rank, hit in enumerate(bm25_hits):
        doc_id = hit['_id']
        increment = 1.0 / (rrf_k + rank + 1)
        if doc_id in scores:
            scores[doc_id]['rrf_score'] += increment
        else:
            scores[doc_id] = {'rrf_score': increment, 'source': hit['_source']}

    ranked = sorted(scores.items(), key=lambda x: x[1]['rrf_score'], reverse=True)

    results = []
    for doc_id, data in ranked[:top_k]:
        src = data['source']
        results.append({
            'abstract_text': src.get('abstract_text', ''),
            'core_rule': src.get('core_rule', ''),
            'filename': src.get('filename', ''),
            'page_number': src.get('page_number', 0),
            'section_identifier': src.get('section_identifier'),
            'statute_codes': src.get('statute_codes', []),
            'raw_text': (src.get('raw_text') or '')[:600],
            'score': data['rrf_score'],
            'state': src.get('state', 'MS'),
            'agency_type': src.get('agency_type', ''),
            'fee_amounts': src.get('fee_amounts', []),
            'testing_requirements': src.get('testing_requirements'),
            'reciprocity_provisions': src.get('reciprocity_provisions'),
            'license_categories': src.get('license_categories', []),
        })

    return results


# ── Term frequency on document records ──────────────────────────────────

def count_term_in_documents(term, index, filter_state=None, filter_states=None):
    """
    Count exact term occurrences across ALL document records using scroll API.

    Searches record_type=document (full text per PDF), not page records.
    Returns total count + per-document breakdown with references.
    """
    filters = [{"term": {"record_type": "document"}}]
    if filter_state:
        filters.append({"term": {"state": filter_state}})
    if filter_states:
        filters.append({"terms": {"state": filter_states}})

    # Match documents containing the term
    query = {
        "size": 100,
        "_source": ["filename", "full_text", "state", "agency_type", "total_pages"],
        "query": {
            "bool": {
                "must": [{"match": {"full_text": term}}],
                "filter": filters,
            }
        }
    }

    response = opensearch_client.search(
        index=index,
        body=query,
        scroll='2m',
    )

    total_count = 0
    per_document = []
    term_lower = term.lower()

    # Process all pages via scroll
    while True:
        hits = response['hits']['hits']
        if not hits:
            break

        for hit in hits:
            src = hit['_source']
            full_text = (src.get('full_text') or '').lower()
            count = full_text.count(term_lower)
            if count > 0:
                total_count += count

                # Find page references
                page_refs = []
                for match in re.finditer(r'\[Page (\d+)\]', src.get('full_text', '')):
                    page_num = int(match.group(1))
                    # Check if term appears near this page marker
                    start = match.start()
                    next_page = src.get('full_text', '').find('[Page ', start + 1)
                    if next_page == -1:
                        next_page = len(src.get('full_text', ''))
                    page_text = src.get('full_text', '')[start:next_page].lower()
                    if term_lower in page_text:
                        page_refs.append(page_num)

                per_document.append({
                    'filename': src.get('filename', ''),
                    'state': src.get('state', 'MS'),
                    'agency_type': src.get('agency_type', ''),
                    'count': count,
                    'pages': page_refs[:20],  # cap references
                })

        scroll_id = response.get('_scroll_id')
        if not scroll_id:
            break
        response = opensearch_client.scroll(scroll_id=scroll_id, scroll='2m')

    # Sort by count descending
    per_document.sort(key=lambda x: x['count'], reverse=True)

    return {
        'total_count': total_count,
        'documents_with_term': len(per_document),
        'breakdown': per_document,
    }


# ── Context formatting ──────────────────────────────────────────────────

def format_context(results):
    """Format page search results into context for LLM."""
    if not results:
        return "No relevant legal documents found for this query."

    parts = []
    for r in results:
        section = r['section_identifier'] or 'N/A'
        state = r.get('state', 'MS')
        statutes = ', '.join(r['statute_codes']) if r['statute_codes'] else 'None identified'

        parts.append("""---
STATE: %s
SOURCE: %s (Section: %s, Page: %s)
RELEVANCE SCORE: %.4f
STATUTE CODES: %s

SUMMARY: %s

CORE RULE: %s

ORIGINAL TEXT (for precise citation):
%s
---""" % (state, r['filename'], section, r['page_number'], r['score'],
          statutes, r['abstract_text'], r.get('core_rule', 'N/A'), r['raw_text']))

    return "\n".join(parts)


# Allowlist of models the frontend may select. Maps a friendly key → Bedrock model id.
# Add new entries here once their Marketplace subscription is active.
ALLOWED_MODELS = {
    'mistral-large-3': 'mistral.mistral-large-3-675b-instruct',
    'kimi-k2.5':       'moonshotai.kimi-k2.5',
    'nova-pro':        'us.amazon.nova-pro-v1:0',
    'nemotron-super-3': 'nvidia.nemotron-super-3-120b',
}


def resolve_model_id(requested):
    """Map a frontend model key to a Bedrock model id. Falls back to env default."""
    if requested and requested in ALLOWED_MODELS:
        return ALLOWED_MODELS[requested]
    return BEDROCK_MODEL_ID


def call_bedrock_llm(user_message, history=None, model_id=None):
    """Call Bedrock LLM via Converse API. `model_id` overrides the env default."""
    messages = []
    if history:
        for msg in history:
            content = msg.get("content", "")
            if isinstance(content, str):
                messages.append({"role": msg["role"], "content": [{"text": content}]})
            else:
                messages.append(msg)
    messages.append({"role": "user", "content": [{"text": user_message}]})

    response = bedrock_client.converse(
        modelId=model_id or BEDROCK_MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=messages,
        inferenceConfig={
            "maxTokens": 2048,  # Capped to keep latency under API Gateway 29s limit
            "temperature": 0.1,
            "topP": 0.9,
        },
    )

    return response['output']['message']['content'][0]['text']


# ── Intent detection ────────────────────────────────────────────────────

# State name → code mapping for detecting cross-state queries
STATE_NAMES = {
    'alabama': 'AL', 'arkansas': 'AR', 'georgia': 'GA', 'louisiana': 'LA',
    'mississippi': 'MS', 'tennessee': 'TN', 'texas': 'TX',
    ' al ': 'AL', ' ar ': 'AR', ' ga ': 'GA', ' la ': 'LA',
    ' ms ': 'MS', ' tn ': 'TN', ' tx ': 'TX',
}


def detect_states(query):
    """Return list of state codes mentioned in the query."""
    q = ' ' + query.lower() + ' '
    found = []
    for name, code in STATE_NAMES.items():
        if name in q and code not in found:
            found.append(code)
    return found


def detect_intent(query):
    """
    Intent detection from query text.

    Returns: 'term_count', 'comparison', 'reciprocity', or 'general'
    """
    q = query.lower()

    # Term counting patterns
    count_patterns = [
        'how many times', 'how often', 'count of', 'frequency of',
        'number of times', 'appearances of', 'occurrences',
    ]
    if any(p in q for p in count_patterns):
        return 'term_count'

    # Reciprocity patterns (special case of cross-state)
    reciprocity_patterns = [
        'reciprocity', 'reciprocal', 'moved to', 'moving to',
        'transfer license', 'licensed in another state',
        'holds a license in', 'held a license in',
    ]
    if any(p in q for p in reciprocity_patterns):
        return 'reciprocity'

    # Comparison patterns
    compare_patterns = [
        'compare', 'comparison', 'how does', 'differ', 'difference',
        'versus', ' vs ', 'other states', 'across states',
    ]
    if any(p in q for p in compare_patterns):
        return 'comparison'

    # If query mentions 2+ states, treat as comparison
    if len(detect_states(query)) >= 2:
        return 'comparison'

    return 'general'


def extract_search_term(query):
    """Extract the term to count from a frequency query."""
    # Look for quoted terms first
    quoted = re.findall(r'["\']([^"\']+)["\']', query)
    if quoted:
        return quoted[0]

    # Common patterns: "how many times does X appear"
    patterns = [
        r'(?:term|word|phrase)\s+["\']?(\w+)["\']?',
        r'(?:does|do)\s+(?:the\s+)?(?:term\s+|word\s+)?["\']?(\w+)["\']?\s+appear',
        r'(?:times|occurrences?\s+of)\s+["\']?(\w+)["\']?',
        r'(?:count|frequency)\s+(?:of\s+)?["\']?(\w+)["\']?',
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


# ── DynamoDB job helpers ────────────────────────────────────────────────

def _create_job(query, mode, filters, history):
    """Create a new pending job in DynamoDB and return job_id."""
    job_id = str(uuid.uuid4())
    now = int(time.time())
    jobs_table.put_item(Item={
        'job_id': job_id,
        'status': 'pending',
        'query': query,
        'mode': mode,
        'filters': filters or {},
        'history_count': len(history) if history else 0,
        'created_at': now,
        'ttl': now + JOB_TTL_SECONDS,
    })
    return job_id


def _update_job(job_id, **fields):
    """Update job fields in DynamoDB."""
    update_expr_parts = []
    expr_attr_names = {}
    expr_attr_vals = {}
    for k, v in fields.items():
        placeholder_name = '#%s' % k
        placeholder_val = ':%s' % k
        update_expr_parts.append('%s = %s' % (placeholder_name, placeholder_val))
        expr_attr_names[placeholder_name] = k
        expr_attr_vals[placeholder_val] = _to_ddb(v)

    jobs_table.update_item(
        Key={'job_id': job_id},
        UpdateExpression='SET ' + ', '.join(update_expr_parts),
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_vals,
    )


def _to_ddb(value):
    """Convert Python types to DynamoDB-safe types (no floats)."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_ddb(v) for v in value]
    return value


def _from_ddb(value):
    """Convert DynamoDB types back to JSON-friendly Python types."""
    if isinstance(value, Decimal):
        return float(value) if value % 1 else int(value)
    if isinstance(value, dict):
        return {k: _from_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_ddb(v) for v in value]
    return value


def _get_job(job_id):
    """Fetch a job by ID. Returns dict or None."""
    resp = jobs_table.get_item(Key={'job_id': job_id})
    item = resp.get('Item')
    return _from_ddb(item) if item else None


# ── Main handler ────────────────────────────────────────────────────────

def lambda_handler(event, context):
    """
    Main Lambda handler — dispatches between three modes:

    1. POST with body → create async job, return 202 + job_id
    2. GET /v2/query/status/{job_id} → return job status + result
    3. Internal async invocation (event has _async_job_id) → process query,
       write result to DynamoDB
    """
    try:
        # ── Mode 1: Internal async invocation ────────────────────────
        if event.get('_async_job_id'):
            return _run_async_job(event)

        # ── Mode 2: HTTP GET (status check) ──────────────────────────
        http_method = event.get('httpMethod', 'POST')
        if http_method == 'OPTIONS':
            return _cors_response()

        if http_method == 'GET':
            return _handle_status_check(event)

        # ── Mode 3: HTTP POST (enqueue + return 202) ─────────────────
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event

        query = body.get('query', '')
        if not query:
            return _error(400, 'Query parameter is required')

        filters = body.get('filters', {}) or {}
        history = body.get('history') or []
        mode = body.get('mode', 'research')
        model = body.get('model')  # frontend-selected model key (allowlisted server-side)

        # If sync=true, run synchronously (for testing or quick queries)
        if body.get('sync'):
            return _process_query_sync(query, mode, filters, history, model)

        # Default: async — create job, dispatch worker, return 202
        job_id = _create_job(query, mode, filters, history)

        # Self-invoke async to do the heavy work
        lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='Event',
            Payload=json.dumps({
                '_async_job_id': job_id,
                'query': query,
                'mode': mode,
                'filters': filters,
                'history': history,
                'model': model,
            }).encode(),
        )

        return {
            'statusCode': 202,
            'headers': _cors_headers(),
            'body': json.dumps({
                'job_id': job_id,
                'status': 'pending',
                'poll_url': '/v2/query/status/%s' % job_id,
            })
        }

    except Exception as e:
        print("Error: %s" % str(e))
        import traceback
        traceback.print_exc()
        return _error(500, str(e))


def _handle_status_check(event):
    """Handle GET requests for job status."""
    path_params = event.get('pathParameters') or {}
    query_string = event.get('queryStringParameters') or {}
    job_id = path_params.get('job_id') or query_string.get('job_id') or ''

    # Fallback: parse from URL path if pathParameters isn't populated
    if not job_id:
        path = event.get('path') or event.get('rawPath') or ''
        match = re.search(r'/status/([A-Za-z0-9\-]+)', path)
        if match:
            job_id = match.group(1)

    if not job_id:
        return _error(400, 'job_id is required')

    job = _get_job(job_id)
    if not job:
        return _error(404, 'Job not found: %s' % job_id)

    # Return whatever fields are present
    response = {
        'job_id': job_id,
        'status': job.get('status', 'unknown'),
    }

    if job.get('status') == 'done':
        response.update({
            'answer': job.get('answer', ''),
            'citations': job.get('citations', []),
            'intent': job.get('intent', 'general'),
            'metadata': job.get('metadata', {}),
        })
    elif job.get('status') == 'failed':
        response['error'] = job.get('error', 'Unknown error')

    return _success(response)


def _run_async_job(event):
    """Worker mode — invoked async to process a query and write to DynamoDB."""
    job_id = event['_async_job_id']
    print("[async] Processing job %s" % job_id)

    try:
        result = _process_query(
            event['query'],
            event.get('mode', 'research'),
            event.get('filters', {}),
            event.get('history', []),
            event.get('model'),
        )

        _update_job(
            job_id,
            status='done',
            answer=result['answer'],
            citations=result['citations'],
            intent=result['intent'],
            metadata=result['metadata'],
            completed_at=int(time.time()),
        )
        print("[async] Job %s completed" % job_id)
        return {'statusCode': 200, 'body': 'ok'}

    except Exception as e:
        print("[async] Job %s failed: %s" % (job_id, e))
        import traceback
        traceback.print_exc()
        _update_job(
            job_id,
            status='failed',
            error=str(e),
            completed_at=int(time.time()),
        )
        return {'statusCode': 500, 'body': str(e)}


def _process_query_sync(query, mode, filters, history, model=None):
    """Run a query synchronously (for debug or quick queries with sync=true)."""
    try:
        result = _process_query(query, mode, filters, history, model)
        return _success({
            'answer': result['answer'],
            'citations': result['citations'],
            'query': query,
            'intent': result['intent'],
            'metadata': result['metadata'],
        })
    except Exception as e:
        return _error(500, str(e))


def _process_query(query, mode, filters, history, model=None):
    """
    Heavy processing — runs the actual search + LLM generation.
    Returns a dict {answer, citations, intent, metadata}.
    """
    filter_state = filters.get('state')
    filter_agency_type = filters.get('agency_type')
    filter_states = filters.get('states')

    intent = detect_intent(query)
    resolved_model_id = resolve_model_id(model)

    # STRICT index routing by UI mode
    target_index = PHASE1_INDEX if mode == 'chat' else PHASE2_INDEX

    # ── Term count branch ───────────────────────────────────────────
    if intent == 'term_count':
        term = extract_search_term(query)
        if not term:
            intent = 'general'  # fall through to general search
        else:
            f_state = filter_state
            f_states = filter_states
            if mode == 'chat' and not f_state and not f_states:
                f_state = "MS"

            freq_data = count_term_in_documents(
                term, target_index, filter_state=f_state, filter_states=f_states,
            )

            freq_summary = "Term: '%s'\nTotal occurrences: %d across %d documents\n\n" % (
                term, freq_data['total_count'], freq_data['documents_with_term'])
            for doc in freq_data['breakdown'][:20]:
                pages_str = ", ".join(str(p) for p in doc['pages'][:10])
                freq_summary += "- %s (%s): %d occurrences (pages: %s)\n" % (
                    doc['filename'], doc['state'], doc['count'], pages_str or 'N/A')

            user_message = """Based on the following term frequency analysis, answer the user's question.

TERM FREQUENCY DATA:
%s

USER QUESTION: %s

Provide the count, list the documents where the term appears, and note any patterns.""" % (
                freq_summary, query)

            answer = call_bedrock_llm(user_message, history=history, model_id=resolved_model_id)

            return {
                'answer': answer,
                'citations': [],
                'intent': 'term_count',
                'metadata': dict(freq_data, model=model or 'default'),
            }

    # ── General / comparison search ─────────────────────────────────
    if mode == 'chat':
        if not filter_state:
            filter_state = "MS"
        filter_states = None

        search_results = search_pages(
            query,
            index=target_index,
            top_k=8,
            filter_state=filter_state,
            filter_agency_type=filter_agency_type,
        )
    else:
        # RESEARCH mode — Phase 2 index
        is_multi_state_query = intent in ('comparison', 'reciprocity')

        if is_multi_state_query:
            if not filter_states:
                detected = detect_states(query)
                if detected:
                    if intent == 'reciprocity' and 'MS' not in detected:
                        detected.insert(0, 'MS')
                    filter_states = detected
                else:
                    filter_states = ["MS", "AL", "LA", "TN", "AR", "GA", "TX"]

            # Per-state budget — kept modest since Mistral is the bottleneck
            # More context = more tokens = longer Mistral latency
            if len(filter_states) <= 2:
                per_state_k = 6
            elif len(filter_states) <= 4:
                per_state_k = 4
            else:
                per_state_k = 3

            search_results = []
            for state in filter_states:
                state_results = search_pages(
                    query,
                    index=target_index,
                    top_k=per_state_k,
                    filter_state=state,
                    filter_agency_type=filter_agency_type,
                )
                search_results.extend(state_results)

            search_results.sort(key=lambda r: r['score'], reverse=True)
        else:
            search_results = search_pages(
                query,
                index=target_index,
                top_k=10,
                filter_state=filter_state,
                filter_agency_type=filter_agency_type,
                filter_states=filter_states,
            )

    ctx = format_context(search_results)

    user_message = """Based on the following legal documents, please answer the user's question.
Remember: You MUST cite specific statutory authority for every claim.

RETRIEVED LEGAL CONTEXT:
%s

USER QUESTION: %s

Provide a clear, well-cited answer. If the context doesn't contain relevant information, clearly state this.""" % (ctx, query)

    answer = call_bedrock_llm(user_message, history=history, model_id=resolved_model_id)

    citations = [
        {
            'document': r['filename'],
            'section': r['section_identifier'],
            'pages': [r['page_number']],
            'statute_codes': r['statute_codes'],
            'relevance': round(r['score'], 3),
            'state': r.get('state', 'MS'),
            'agency_type': r.get('agency_type', ''),
        }
        for r in search_results
    ]

    return {
        'answer': answer,
        'citations': citations,
        'intent': intent,
        'metadata': {
            'mode': mode,
            'index_used': target_index,
            'states_searched': filter_states or ([filter_state] if filter_state else []),
            'model': model or 'default',
        },
    }


# ── HTTP response helpers ───────────────────────────────────────────────

def _cors_headers():
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    }


def _cors_response():
    return {
        'statusCode': 200,
        'headers': _cors_headers(),
        'body': '',
    }


def _success(body):
    return {
        'statusCode': 200,
        'headers': _cors_headers(),
        'body': json.dumps(body),
    }


def _error(status, message):
    return {
        'statusCode': status,
        'headers': _cors_headers(),
        'body': json.dumps({'error': message}),
    }
