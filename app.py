from collections import defaultdict, deque
from time import monotonic

from flask import Flask, jsonify, render_template, request

from config import settings
from services.gemini_service import (
    GeminiConfigurationError,
    GeminiRequestError,
    GeminiService,
)
from services.knowledge_service import KnowledgeService


def create_app(test_config=None, knowledge=None, gemini=None):
    application = Flask(
        __name__,
        static_folder="templates",
        static_url_path="",
    )
    application.config.update(test_config or {})
    application.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    application.settings = settings
    application.knowledge = knowledge or KnowledgeService(settings.knowledge_base_dir)
    application.gemini = gemini or GeminiService(
        settings.gemini_api_key,
        settings.gemini_model,
    )
    request_times = defaultdict(deque)

    @application.before_request
    def enforce_chat_rate_limit():
        if request.endpoint not in {"chat", "test_gemini"}:
            return None
        now = monotonic()
        recent = request_times[request.remote_addr or "unknown"]
        while recent and now - recent[0] >= 60:
            recent.popleft()
        if len(recent) >= settings.max_requests_per_minute:
            return jsonify({"error": "Too many requests. Please wait a minute and try again."}), 429
        recent.append(now)
        return None

    @application.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": "The request is too large. Please shorten the message and retry."}), 413

    @application.errorhandler(500)
    def internal_server_error(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "The server could not complete the request. Please try again."}), 500
        return "The server could not complete the request. Please try again.", 500

    @application.get("/")
    def index():
        return render_template("index.html")

    @application.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @application.get("/api/config-check")
    def config_check():
        return jsonify(
            {
                "api_key_present": application.gemini.api_key != "",
                "model_configured": application.gemini.model != "",
                "gemini_configured": application.gemini.configured,
            }
        )

    @application.post("/api/test-gemini")
    def test_gemini():
        if not application.gemini.configured:
            return jsonify(
                {"status": "not_configured", "message": "Configure the API key and model on the server."}
            ), 503
        try:
            answer = application.gemini.generate(
                "Reply with the words: Gemini connection successful.",
                {"documents": [], "faqs": []},
                [],
            )
        except GeminiConfigurationError:
            return jsonify({"status": "not_configured", "message": "Gemini is not configured."}), 503
        except GeminiRequestError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 502
        return jsonify({"status": "ok", "answer": answer})

    @application.post("/api/chat")
    def chat():
        if not request.is_json:
            return jsonify({"error": "Send a JSON request with a message field."}), 400
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "The request body must be a JSON object."}), 400
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            return jsonify({"error": "Please enter a message before sending."}), 400
        message = message.strip()
        if len(message) > settings.max_message_length:
            return jsonify(
                {"error": f"Message is too long. The limit is {settings.max_message_length} characters."}
            ), 400

        conversation = payload.get("conversation", [])
        if not isinstance(conversation, list) or len(conversation) > settings.max_history_messages:
            return jsonify({"error": "Conversation history is invalid or too long."}), 400
        safe_history = []
        for item in conversation:
            if not isinstance(item, dict) or item.get("role") not in {"assistant", "user"}:
                return jsonify({"error": "Conversation history contains an invalid message."}), 400
            content = item.get("content")
            if not isinstance(content, str) or len(content) > settings.max_message_length:
                return jsonify({"error": "Conversation history contains an invalid message."}), 400
            safe_history.append({"role": item["role"], "content": content})

        documents = application.knowledge.retrieve(message)
        faqs = application.knowledge.find_faq(message)
        sources = list(
            dict.fromkeys(
                [item["source"] for item in documents]
                + [item["source"] for item in faqs if item.get("source")]
            )
        )
        context = {"documents": documents, "faqs": faqs}

        needs_verified_source = application.knowledge.requires_verified_source(message)
        if needs_verified_source and not documents:
            answer = application.knowledge.answer_without_model(message)
            status = "unverified"
        elif not application.gemini.configured:
            answer = application.knowledge.answer_without_model(message, documents)
            status = "fallback"
        else:
            try:
                answer = application.gemini.generate(message, context, safe_history)
            except GeminiConfigurationError:
                return jsonify({"error": "Gemini is not configured. Check the server configuration."}), 503
            except GeminiRequestError as exc:
                return jsonify({"error": str(exc), "retry": True}), 502
            status = "ok"

        response_payload = {
            "answer": answer,
            "sources": sources,
            "status": status,
        }
        if status == "fallback":
            response_payload["note"] = "Gemini is not configured; this response uses local guidance only."
        return jsonify(response_payload)

    return application


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
