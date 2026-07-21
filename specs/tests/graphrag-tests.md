# GraphRAG Unit & Integration Tests

## Unit Tests (`tests/unit/features/test_graphrag.py`)

```python
def test_upload_creates_pending_document_record(test_client, auth_headers, test_db):
    """POST /knowledge/upload → 202, knowledge_documents row with status 'pending'."""
    with open("tests/fixtures/knowledge/test_domain_doc.txt", "rb") as f:
        response = test_client.post(
            "/api/v1/knowledge/upload",
            files={"file": ("test_domain_doc.txt", f, "text/plain")},
            headers=auth_headers,
        )
    assert response.status_code == 202
    doc_id = response.json()["id"]
    row = test_db.query("SELECT * FROM knowledge_documents WHERE id = $1", doc_id).fetchone()
    assert row["graphrag_status"] == "pending"

def test_upload_rejects_unsupported_extension(test_client, auth_headers):
    """POST /knowledge/upload with .exe file → 415."""
    response = test_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers=auth_headers,
    )
    assert response.status_code == 415

def test_upload_rejects_file_over_50mb(test_client, auth_headers, mocker):
    """POST /knowledge/upload with a file > 50MB → 413."""
    large_content = b"x" * (51 * 1024 * 1024)
    response = test_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("big.pdf", large_content, "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 413

def test_upload_filename_sanitized_to_prevent_path_traversal(test_client, auth_headers, mocker):
    """Filename with '../' is sanitized before writing to DATA_DIR."""
    mock_write = mocker.patch("graphrag.ingestion.write_to_data_dir")
    test_client.post(
        "/api/v1/knowledge/upload",
        files={"file": ("../../etc/passwd", b"root:x:0:0", "text/plain")},
        headers=auth_headers,
    )
    # secure_filename() must strip path traversal
    call_args = mock_write.call_args[0]
    assert ".." not in call_args[0]
    assert "passwd" not in call_args[0] or "/" not in call_args[0]

def test_cost_estimate_calculated_from_file_size():
    """Cost estimate = (file_size_bytes / 4) * 15 / 1000 * price_per_1k_tokens."""
    # 4MB file, 15x multiplier, GPT-4 price as proxy
    estimate = estimate_graphrag_cost(file_size_bytes=4 * 1024 * 1024)
    # Should be non-zero and in the "dollars, not cents" range for a 4MB doc
    assert estimate > 1.0
    assert estimate < 100.0

def test_cost_estimate_above_threshold_returns_warning_flag():
    """estimate > $5.00 → requires_confirmation=True."""
    result = check_cost_and_confirm(file_size_bytes=50 * 1024 * 1024, threshold=5.0)
    assert result.requires_confirmation is True
    assert result.estimated_cost > 5.0

def test_cost_estimate_below_threshold_no_warning():
    """Tiny file → requires_confirmation=False."""
    result = check_cost_and_confirm(file_size_bytes=10 * 1024, threshold=5.0)
    assert result.requires_confirmation is False

def test_pdf_text_extraction_returns_non_empty_string(tmp_path):
    """PDF extraction produces non-empty text for a valid test PDF."""
    pdf_path = "tests/fixtures/knowledge/test_domain_doc.pdf"
    text = extract_text_from_file(pdf_path, "application/pdf")
    assert len(text) > 50

def test_txt_extraction_returns_file_contents(tmp_path):
    """TXT extraction returns the file contents."""
    f = tmp_path / "doc.txt"
    f.write_text("Domain knowledge: revenue is defined as net_amount minus refunds.")
    text = extract_text_from_file(str(f), "text/plain")
    assert "net_amount" in text

def test_graphrag_retrieval_with_no_documents_returns_empty_context():
    """No documents indexed → retrieval returns empty GraphRAGContext."""
    context = retrieve_graphrag_context(question="What is churn?", summaries="...", doc_count=0)
    assert context.relevant_entities == []
    assert context.community_summaries == []

def test_graphrag_context_appended_after_summaries_in_planner_prompt(mock_llm):
    """GraphRAG context appears after data summaries in Planner prompt."""
    llm = mock_llm(["Step 1"])
    run_planner_init(
        question="What is churn?",
        summaries="customers: customer_id, churn_date",
        graphrag_context="Domain: churn means the customer cancelled their subscription",
        llm=llm
    )
    prompt = str(llm.invoke.call_args[0][0])
    summaries_pos = prompt.index("customers: customer_id")
    graphrag_pos = prompt.index("churn means the customer cancelled")
    assert summaries_pos < graphrag_pos  # graphrag after summaries

def test_delete_document_triggers_full_index_rebuild(mocker, test_db):
    """Deleting a document enqueues a GraphRAG full rebuild job."""
    mock_rebuild = mocker.patch("graphrag.indexing.run_full_rebuild")
    doc_id = create_indexed_document(db=test_db)
    delete_knowledge_document(doc_id, db=test_db)
    mock_rebuild.assert_called_once()

def test_delete_document_removes_entities_from_db(test_db):
    """After delete, knowledge_entities for that document are removed."""
    doc_id = create_indexed_document_with_entities(entity_count=10, db=test_db)
    delete_knowledge_document(doc_id, db=test_db)
    count = test_db.query("SELECT COUNT(*) FROM knowledge_entities WHERE doc_id = $1", doc_id).scalar()
    assert count == 0

def test_get_knowledge_document_shows_entity_and_community_counts(test_client, auth_headers, test_db):
    """GET /knowledge/{doc_id} returns entity_count and community_count."""
    doc_id = create_indexed_document_with_entities(entity_count=5, community_count=3, db=test_db)
    response = test_client.get(f"/api/v1/knowledge/{doc_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["entity_count"] == 5
    assert response.json()["community_count"] == 3

def test_get_knowledge_document_does_not_return_file_content(test_client, auth_headers, test_db):
    """GET /knowledge/{doc_id} must NOT return file content, only metadata."""
    doc_id = create_indexed_document(db=test_db)
    response = test_client.get(f"/api/v1/knowledge/{doc_id}", headers=auth_headers)
    body = response.text
    assert "Domain knowledge:" not in body   # file content must not leak

def test_indexing_failure_sets_status_failed_and_error_message(mocker, test_db):
    """If GraphRAG indexing fails, status → 'failed' and error_message is stored."""
    mocker.patch("graphrag.indexing.run_graphrag_index", side_effect=RuntimeError("LLM quota exceeded"))
    doc_id = create_pending_document(db=test_db)
    run_indexing_job(doc_id, db=test_db)
    row = test_db.query("SELECT * FROM knowledge_documents WHERE id = $1", doc_id).fetchone()
    assert row["graphrag_status"] == "failed"
    assert "LLM quota exceeded" in row["error_message"]

def test_on_prem_uses_ollama_llm_for_graphrag(mocker):
    """On-prem deployment: GraphRAG settings use Ollama LLM endpoint."""
    mocker.patch("config.get", return_value={"deployment": {"provider": "on_prem"}, "llm": {"provider": "ollama"}})
    settings = build_graphrag_settings()
    assert "ollama" in settings["llm"]["api_base"].lower()
    assert settings["llm"]["model"] == "llama3"  # or configured ollama model
```

---

## Integration Tests (`tests/integration/features/test_graphrag_integration.py`)

```python
@pytest.mark.integration
def test_upload_and_index_5_page_doc_completes(test_client, auth_headers, real_db, real_graphrag):
    """Uploading the 5-page test document results in graphrag_status: indexed."""
    with open("tests/fixtures/knowledge/test_domain_doc.txt", "rb") as f:
        response = test_client.post(
            "/api/v1/knowledge/upload",
            files={"file": ("test_domain_doc.txt", f, "text/plain")},
            headers=auth_headers,
        )
    doc_id = response.json()["id"]

    # Wait for async indexing to complete (max 120 seconds for integration)
    for _ in range(24):
        doc = test_client.get(f"/api/v1/knowledge/{doc_id}", headers=auth_headers).json()
        if doc["graphrag_status"] == "indexed":
            break
        time.sleep(5)

    assert doc["graphrag_status"] == "indexed"
    assert doc["entity_count"] > 0
    assert doc["community_count"] > 0

@pytest.mark.integration
def test_planner_retrieval_returns_context_matching_document(real_llm, real_graphrag):
    """After indexing, Planner retrieval returns context relevant to the domain doc."""
    # test_domain_doc.txt contains info about "net_amount", "revenue", "churn"
    context = retrieve_graphrag_context(
        question="What is the definition of churn in this dataset?",
        summaries="customers: customer_id, churn_date, net_amount"
    )
    all_text = " ".join([e.description for e in context.relevant_entities] + context.community_summaries)
    assert "churn" in all_text.lower()

@pytest.mark.integration
def test_delete_and_reindex_removes_document_entities(test_client, auth_headers, real_db, real_graphrag):
    """After delete + rebuild, document's entities are gone from knowledge graph."""
    doc_id = create_and_wait_for_indexed_document(test_client, auth_headers)
    entity_count_before = test_client.get(
        f"/api/v1/knowledge/{doc_id}", headers=auth_headers
    ).json()["entity_count"]
    assert entity_count_before > 0

    test_client.delete(f"/api/v1/knowledge/{doc_id}", headers=auth_headers)
    # Wait for rebuild
    time.sleep(30)

    row = real_db.query("SELECT COUNT(*) FROM knowledge_entities WHERE doc_id = $1", doc_id).scalar()
    assert row == 0
```

---

## Test Fixture: `tests/fixtures/knowledge/test_domain_doc.txt`

```
# Business Domain Reference — Analytics Team

## Revenue Definitions
- net_amount: The final revenue amount after applying all discounts, refunds, and adjustments.
  This is the primary revenue metric used in financial reporting.
- gross_amount: Revenue before deductions. Not used in standard KPI dashboards.
- Monthly Recurring Revenue (MRR): Sum of net_amount for all active subscriptions in a calendar month.

## Customer Churn
- Churn is defined as a customer who has not placed an order in the last 90 days AND has
  a recorded churn_date in the customers table.
- Churn rate = (churned customers in period) / (active customers at start of period) * 100
- A customer is considered "at risk" if their last_order_date is more than 60 days ago.

## Product Categories
- Electronics: Includes Widgets and Gadgets. High margin, fast-moving.
- Furniture: Includes Doodads and large items. Lower margin, slower moving.

## Regional Definitions
- North region: Customers with region = 'North' in the customers table.
- South region: Customers with region = 'South'.
- Q3 2024 is defined as order_date BETWEEN '2024-07-01' AND '2024-09-30' (inclusive).
```
