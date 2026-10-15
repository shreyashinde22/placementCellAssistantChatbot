import pytest

from app import create_app
from config import settings
from services.knowledge_service import KnowledgeService


class StubGemini:
    def __init__(self, configured=False):
        self.api_key = "test-only-secret-marker" if configured else ""
        self.model = "test-model" if configured else ""
        self.configured = configured
        self.calls = []

    def generate(self, message, context, history):
        self.calls.append(
            {"message": message, "context": context, "history": history}
        )
        return "A mocked, grounded answer."


@pytest.fixture
def knowledge_base(tmp_path):
    base_dir = tmp_path / "knowledge_base"
    verified_dir = base_dir / "verified_college_information"
    verified_dir.mkdir(parents=True)
    (verified_dir / "placement-policy.txt").write_text(
        "The official placement notice describes the eligibility criteria for the campus placement drive.",
        encoding="utf-8",
    )
    (base_dir / "faqs.json").write_text("[]", encoding="utf-8")
    return KnowledgeService(base_dir)


@pytest.fixture
def make_client(knowledge_base):
    clients = []

    def factory(gemini=None, knowledge=None):
        selected_gemini = gemini or StubGemini()
        application = create_app(
            {"TESTING": True},
            knowledge=knowledge or knowledge_base,
            gemini=selected_gemini,
        )
        clients.append((application.test_client(), selected_gemini))
        return clients[-1]

    return factory


def test_index_and_health_routes(make_client):
    client, _ = make_client()

    page = client.get("/")
    assert page.status_code == 200
    assert b"Placement Cell Assistant" in page.data
    assert b'href="/style.css"' in page.data
    assert b'src="/app.js"' in page.data
    assert client.get("/style.css").status_code == 200
    assert client.get("/app.js").status_code == 200
    assert client.get("/api/health").get_json() == {"status": "ok"}


def test_config_check_reports_presence_without_exposing_key(make_client):
    gemini = StubGemini(configured=True)
    client, _ = make_client(gemini=gemini)

    response = client.get("/api/config-check")

    assert response.status_code == 200
    assert response.get_json() == {
        "api_key_present": True,
        "model_configured": True,
        "gemini_configured": True,
    }
    assert b"test-only-secret-marker" not in response.data


@pytest.mark.parametrize(
    ("body", "content_type", "expected_error"),
    [
        (None, "text/plain", "Send a JSON request"),
        ([], "application/json", "JSON object"),
        ({}, "application/json", "enter a message"),
        ({"message": "  "}, "application/json", "enter a message"),
        ({"message": "x" * (settings.max_message_length + 1)}, "application/json", "too long"),
        ({"message": "Hello", "conversation": {}}, "application/json", "history is invalid"),
        (
            {"message": "Hello", "conversation": [{"role": "system", "content": "No"}]},
            "application/json",
            "invalid message",
        ),
        (
            {"message": "Hello", "conversation": [{"role": "user", "content": 42}]},
            "application/json",
            "invalid message",
        ),
    ],
)
def test_chat_request_validation(make_client, body, content_type, expected_error):
    client, _ = make_client()

    response = client.post("/api/chat", json=body) if content_type == "application/json" else client.post(
        "/api/chat", data="not json", content_type=content_type
    )

    assert response.status_code == 400
    assert expected_error.lower() in response.get_json()["error"].lower()


def test_chat_rejects_history_over_limit(make_client):
    client, _ = make_client()
    history = [{"role": "user", "content": "Earlier"}] * (
        settings.max_history_messages + 1
    )

    response = client.post(
        "/api/chat",
        json={"message": "Current question", "conversation": history},
    )

    assert response.status_code == 400
    assert "history is invalid or too long" in response.get_json()["error"]


def test_missing_gemini_uses_safe_fallback(make_client):
    client, gemini = make_client(gemini=StubGemini())

    response = client.post(
        "/api/chat",
        json={"message": "Can you coach me on debugging recursion?"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "fallback"
    assert "authorised placement cell" in payload["answer"]
    assert gemini.calls == []
    assert client.post("/api/test-gemini").status_code == 503


def test_mocked_gemini_receives_retrieved_documents_and_history(make_client):
    gemini = StubGemini(configured=True)
    client, _ = make_client(gemini=gemini)

    response = client.post(
        "/api/chat",
        json={
            "message": "What are the placement eligibility criteria?",
            "conversation": [{"role": "user", "content": "Earlier question"}],
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "answer": "A mocked, grounded answer.",
        "sources": ["knowledge_base/verified_college_information/placement-policy.txt"],
        "status": "ok",
    }
    assert gemini.calls[0]["history"] == [
        {"role": "user", "content": "Earlier question"}
    ]
    documents = gemini.calls[0]["context"]["documents"]
    assert documents
    assert all(document["verified"] for document in documents)
    assert any("eligibility criteria" in document["text"].lower() for document in documents)


def test_relevant_document_is_retrieved_and_cited_without_gemini(make_client):
    client, _ = make_client()

    response = client.post(
        "/api/chat",
        json={"message": "Tell me about placement eligibility criteria"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "fallback"
    assert payload["sources"] == [
        "knowledge_base/verified_college_information/placement-policy.txt"
    ]


def test_unknown_official_question_is_not_invented(make_client):
    client, _ = make_client()

    response = client.post(
        "/api/chat",
        json={"message": "Zorblax recruitment policy?"},
    )

    answer = response.get_json()["answer"].lower()
    assert response.get_json()["sources"] == []
    assert "do not have verified information" in answer
    assert "official placement notice" in answer
    assert "placement cell" in answer


def test_gemini_connection_route_uses_mock_and_does_not_leak_credentials(make_client):
    gemini = StubGemini(configured=True)
    client, _ = make_client(gemini=gemini)

    response = client.post("/api/test-gemini")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "answer": "A mocked, grounded answer.",
    }
    assert b"test-only-secret-marker" not in response.data
    assert len(gemini.calls) == 1
