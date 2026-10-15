import json
import logging
import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_DOCUMENT_BYTES = 2_000_000
MAX_DOCUMENT_CHARS = 100_000
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120
OFFICIAL_QUERY_TERMS = {
    "backlog", "backlogs", "company", "companies", "criteria", "cutoff", "deadline",
    "deadlines", "eligibility", "official", "placement", "placements", "policy",
    "policies", "package", "packages", "recruiter", "recruiters", "recruitment",
    "salary", "salaries", "statistics", "notice", "notices",
}
STOP_WORDS = {
    "a", "an", "and", "are", "can", "for", "from", "how", "i", "in", "is",
    "it", "me", "my", "of", "on", "or", "the", "to", "what", "when", "where",
    "which", "who", "why", "with", "you", "your",
}
logger = logging.getLogger(__name__)


def _tokens(text):
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", text.lower())
        if token not in STOP_WORDS
    }


def _chunks(text):
    clean_text = re.sub(r"\s+", " ", text).strip()
    start = 0
    while start < len(clean_text):
        end = min(start + CHUNK_SIZE, len(clean_text))
        yield clean_text[start:end]
        if end == len(clean_text):
            break
        start = end - CHUNK_OVERLAP


class KnowledgeService:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.verified_dir = self.base_dir / "verified_college_information"
        self.faqs = self._load_faqs()
        self.documents = self._load_documents()

    def _load_faqs(self):
        path = self.base_dir / "faqs.json"
        with path.open(encoding="utf-8") as source:
            entries = json.load(source)
        if not isinstance(entries, list):
            raise ValueError(f"{path} must contain a JSON list.")
        return entries

    def _read_document(self, path):
        if path.stat().st_size > MAX_DOCUMENT_BYTES:
            return ""
        if path.suffix.lower() == ".pdf":
            pages = PdfReader(str(path)).pages
            text = "\n".join(page.extract_text() or "" for page in pages)
        else:
            text = path.read_text(encoding="utf-8")
        return text[:MAX_DOCUMENT_CHARS]

    def _load_documents(self):
        if not self.verified_dir.is_dir():
            return []
        entries = []
        for path in sorted(self.verified_dir.rglob("*")):
            if (
                not path.is_file()
                or path.name.lower() == "readme.md"
                or path.suffix.lower() not in SUPPORTED_EXTENSIONS
            ):
                continue
            try:
                resolved_path = path.resolve(strict=True)
                if not resolved_path.is_relative_to(self.verified_dir.resolve()):
                    continue
                text = self._read_document(path)
            except (OSError, UnicodeDecodeError, ValueError, PdfReadError):
                logger.warning("Skipping unreadable knowledge document: %s", path.name)
                continue
            relative_source = path.relative_to(self.base_dir.parent).as_posix()
            for chunk in _chunks(text):
                entries.append(
                    {
                        "text": chunk,
                        "source": relative_source,
                        "verified": True,
                    }
                )
        return entries

    def retrieve(self, query, limit=3):
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        ranked = []
        for document in self.documents:
            overlap = query_tokens.intersection(_tokens(document["text"]))
            if overlap:
                ranked.append((len(overlap) / len(query_tokens), document))
        ranked.sort(key=lambda result: result[0], reverse=True)
        return [
            {"text": item["text"], "source": item["source"], "verified": True}
            for score, item in ranked[:limit]
            if score > 0
        ]

    def find_faq(self, query, limit=2):
        query_tokens = _tokens(query)
        matches = []
        for entry in self.faqs:
            searchable = " ".join(
                [entry.get("question", ""), entry.get("answer", "")]
                + entry.get("keywords", [])
            )
            overlap = query_tokens.intersection(_tokens(searchable))
            if overlap:
                matches.append((len(overlap), entry))
        matches.sort(key=lambda result: result[0], reverse=True)
        return [item for score, item in matches[:limit] if score]

    def requires_verified_source(self, query):
        query_lower = query.lower()
        if _tokens(query).intersection(OFFICIAL_QUERY_TERMS):
            return True
        return any(
            phrase in query_lower
            for phrase in (
                "selection process",
                "interview stages",
                "recruitment stages",
                "placement drive",
                "placement dates",
                "placement data",
                "placement record",
                "company requirement",
                "company requirements",
                "company-specific",
                "official notice",
                "placement cell contact",
            )
        )

    def answer_without_model(self, query, documents=None):
        if documents:
            passage = documents[0]["text"]
            return (
                "Relevant passage from the authorised knowledge base:\n\n"
                f"> {passage}\n\n"
                "Review the cited document for full context. For time-sensitive details, confirm "
                "with the official placement cell."
            )

        matches = self.find_faq(query)
        if matches:
            entry = matches[0]
            answer = entry.get("answer", "")
            if entry.get("category") == "career-prep":
                return (
                    f"{answer}\n\nThis is general career guidance, not an official college or "
                    "company requirement."
                )
            return (
                f"{answer}\n\nThis is illustrative general guidance, not verified SNJB policy. "
                "Please confirm current requirements with the official placement cell."
            )

        return (
            "I do not have verified information to answer that institutional or company-specific "
            "question. Please check the latest official placement notice or contact the authorised "
            "placement cell. I can still help with general CV, aptitude, coding, and interview preparation."
        )
