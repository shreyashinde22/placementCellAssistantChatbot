# SNJB Placement Cell Assistant

A Flask-based student career assistant with a responsive chat interface. It retrieves matching passages from authorised local documents and can send the question and retrieved context to Gemini. In the absence of Gemini configuration, the app gives safe fallback guidance from its local knowledge base.

## Requirements

- Windows PowerShell
- Python 3.10 or newer
- A Gemini API key is optional for local fallback answers and required for model-generated answers

## Setup (PowerShell)

Run these commands from the project folder:

```powershell
Set-Location "C:\path\to\PlacemenCelChatbot"
py -3 --version
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Set `GEMINI_API_KEY` and `GEMINI_MODEL` in `.env` for Gemini-backed responses. Keep the key private; do not commit `.env` or paste credentials into chat. Leave either value unset to use local fallback guidance.

## Run the app

With the virtual environment activated:

```powershell
python app.py
```

Open <http://127.0.0.1:5000/> in a browser. The local development server binds to loopback and is not intended for production.

## Check configuration and Gemini connectivity

Keep the app running in its own PowerShell window. In another window, run:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/config-check" | ConvertTo-Json
```

The response reports whether the API key, model, and complete Gemini configuration are present. It never returns the key itself. To make a live Gemini connection check:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:5000/api/test-gemini" -ContentType "application/json"
```

This makes a real request to Gemini. A `503` means configuration is missing, and a `502` reports a safe service error. Do not use the connection test in automated tests or production health probes; it consumes an API request.

## Run tests

From the project folder with dependencies installed:

```powershell
python -m pytest -q
```

The tests use temporary knowledge-base files and mocked Gemini clients; they do not require network access or a real API key.

## Knowledge base and missing college details

No verified SNJB placement policies, placement statistics, recruiter relationships, employer criteria, deadlines, or staff contacts are included with this starter project. The sample entries in `knowledge_base/faqs.json` are illustrative guidance only, not official college policy. The knowledge-base README also records that no placement-specific institutional information has been verified.

To add approved documents, place authorised `.txt`, `.md`, or text-readable `.pdf` files in `knowledge_base/verified_college_information/`. Review accuracy, currency, audience, and permission before adding them. Documents are loaded at application startup; restart the app after changes. Scanned PDFs without extractable text will not be searchable. Do not add student records or confidential material. Confirm current college requirements with an authorised placement-cell channel.

## Modules and API

- `app.py` creates the Flask app, serves the UI, validates chat requests, applies an in-memory per-client rate limit, retrieves context, and exposes `/api/health`, `/api/config-check`, `/api/test-gemini`, and `/api/chat`.
- `config.py` loads `GEMINI_API_KEY` and `GEMINI_MODEL` from the environment or `.env` file.
- `services/knowledge_service.py` loads FAQ examples and approved documents, retrieves relevant passages, and provides conservative local fallback answers.
- `services/gemini_service.py` builds grounded prompts for Gemini and returns sanitised service errors.
- `templates/index.html`, `static/css/style.css`, and `static/js/app.js` provide the accessible responsive chat interface. The browser sends `{ "message": "...", "conversation": [...] }` to `/api/chat`.
- `knowledge_base/` contains illustrative FAQs and the folder reserved for verified college information.

The chat API accepts user and assistant history messages, up to the configured history limit, and returns an answer, source filenames, and a status (`ok` or `fallback`). Requests and messages have server-side size limits.

## Production and deployment

- Do not deploy Flask's built-in development server. Run behind a production WSGI server such as Waitress, with HTTPS terminated by a properly configured reverse proxy.
- For a basic Windows host, install Waitress in the environment and launch from the project folder:

  ```powershell
  python -m pip install waitress
  waitress-serve --host=127.0.0.1 --port=5000 app:app
  ```

- Supply `GEMINI_API_KEY` and `GEMINI_MODEL` through the hosting platform's secret/environment configuration. Do not commit secrets; restrict access to logs and configuration.
- Configure the reverse proxy, firewall, TLS, process supervision, request-size limits, and monitoring for the deployment. The current rate limit is held in process memory, so it is not shared across workers or instances.
- Review the knowledge-base documents and Gemini data-handling requirements before production use. The app has no authentication, staff administration, or document upload workflow; deploy it only in an environment appropriate for those limitations.
