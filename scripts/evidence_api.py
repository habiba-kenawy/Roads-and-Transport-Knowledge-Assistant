"""AT-11 evidence: valid responses match the Pydantic models; invalid requests get controlled errors; a slow run gets a 504.

Usage (API running on port 8010; makes a few real model calls): python -m scripts.evidence_api
The 504 case starts its own short-lived server on port 8011 with a 1-second request deadline and a temporary checkpoint database.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from app.schemas.chat import ChatResponse
from app.schemas.search import SearchResponse

API = "http://127.0.0.1:8010"
SHORT_API = "http://127.0.0.1:8011"
OUT_PATH = Path("evidence/AT-11_api.txt")
lines: list[str] = []


def show(title: str, response: httpx.Response, note: str = "") -> None:
    """Record one request's outcome: status and body (the body is cut short, never a stack trace)."""
    body = response.text if len(response.text) < 260 else response.text[:260] + " ..."
    lines.append(f"{title}\n  -> HTTP {response.status_code} {note}\n  {body}\n")


def invalid_requests(client: httpx.Client) -> None:
    """Every kind of invalid input the assignment names must give a 422 that says which field is wrong."""
    lines.append("=== Invalid requests (expect 422, with the field named)\n")
    cases = [
        ("POST /chat  empty message", "/chat", {"message": ""}),
        ("POST /chat  message of 2001 characters (limit 2000)", "/chat", {"message": "x" * 2001}),
        ("POST /chat  top_k 21 (limit 20)", "/chat", {"message": "hi", "top_k": 21}),
        ("POST /chat  top_k 0 (minimum 1)", "/chat", {"message": "hi", "top_k": 0}),
        ("POST /chat  unsupported search mode", "/chat", {"message": "hi", "search_mode": "fuzzy"}),
        ("POST /chat  filter of the wrong type (year is text)", "/chat", {"message": "hi", "filters": {"year": "abc"}}),
        ("POST /chat  invalid thread id", "/chat", {"message": "hi", "thread_id": "bad id!"}),
        ("POST /chat  unknown field", "/chat", {"message": "hi", "colour": "red"}),
        ("POST /search  empty query", "/search", {"query": ""}),
        ("POST /search  unsupported mode", "/search", {"query": "toll", "mode": "fuzzy"}),
        ("POST /search  top_k 21", "/search", {"query": "toll", "top_k": 21}),
        ("POST /chat/resume  missing fields", "/chat/resume", {"thread_id": "t1"}),
    ]
    for title, path, body in cases:
        show(title, client.post(API + path, json=body))


def valid_requests(client: httpx.Client) -> tuple[str, str]:
    """Valid calls: the body is validated against the same Pydantic model the API uses. Returns the paused thread's id and interrupt id."""
    lines.append("=== Valid requests (the response is validated against the Pydantic model)\n")
    show("GET /health", client.get(API + "/health"))

    search = client.post(API + "/search", json={"query": "departure fee airports", "mode": "lexical", "top_k": 2})
    parsed = SearchResponse.model_validate(search.json())
    show("POST /search  lexical, top_k 2", search, f"(valid SearchResponse: {len(parsed.results)} results, stage={parsed.ranking_stage}, score_type={parsed.results[0].score_type})")

    answered = client.post(API + "/chat", json={"message": "How much is the departure fee for passengers leaving through Dubai airports?", "search_mode": "lexical", "top_k": 3})
    chat = ChatResponse.model_validate(answered.json())
    show("POST /chat  a supported question", answered, f"(valid ChatResponse: status={chat.status}, {len(chat.citations)} citations)")

    asked = client.post(API + "/chat", json={"message": "What is the fine?", "search_mode": "lexical"})
    paused = ChatResponse.model_validate(asked.json())
    show("POST /chat  an ambiguous question", asked, f"(valid ChatResponse: status={paused.status}, clarification={paused.clarification is not None})")
    return paused.thread_id, paused.clarification.interrupt_id


def invalid_resumes(client: httpx.Client, thread_id: str, interrupt_id: str) -> None:
    """Resumes and messages the paused thread must refuse (409), and finally the one valid resume."""
    lines.append("=== Invalid and valid resumes (expect 409 for the invalid ones, and the pending question stays pending)\n")
    show("POST /chat/resume  a thread that does not exist", client.post(API + "/chat/resume", json={"thread_id": "no-such-thread", "interrupt_id": "x", "message": "hi"}))
    show("POST /chat/resume  right thread, wrong interrupt id", client.post(API + "/chat/resume", json={"thread_id": thread_id, "interrupt_id": "wrong", "message": "hi"}))
    show("POST /chat  a new message on the paused thread", client.post(API + "/chat", json={"message": "something else", "thread_id": thread_id}))
    resumed = client.post(API + "/chat/resume", json={"thread_id": thread_id, "interrupt_id": interrupt_id, "message": "the departure fee for airport passengers"})
    parsed = ChatResponse.model_validate(resumed.json())
    show("POST /chat/resume  the correct resume", resumed, f"(valid ChatResponse: status={parsed.status})")
    show("POST /chat/resume  the same resume again (nothing is pending any more)", client.post(API + "/chat/resume", json={"thread_id": thread_id, "interrupt_id": interrupt_id, "message": "again"}))


def slow_request() -> None:
    """A second server with a 1-second request deadline: the real question needs longer, so the caller gets a 504, and the busy rule shows."""
    lines.append("=== A request that outlives the deadline (REQUEST_TIMEOUT_SECONDS=1 on a separate server, port 8011)\n")
    env = {**os.environ, "REQUEST_TIMEOUT_SECONDS": "1", "CHECKPOINT_DB_PATH": str(Path(tempfile.mkdtemp()) / "checkpoints.sqlite")}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.api.main:app", "--port", "8011"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(timeout=60) as client:
            for _ in range(60):
                try:
                    if client.get(SHORT_API + "/health").status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.5)
            body = {"message": "Do I need a permit to import or sell a drone in Dubai?", "thread_id": "slow-demo", "search_mode": "hybrid"}
            started = time.perf_counter()
            first = client.post(SHORT_API + "/chat", json=body)
            show("POST /chat  a real question, deadline 1 s", first, f"(returned after {time.perf_counter() - started:.1f} s)")
            show("POST /chat  the same thread straight away", client.post(SHORT_API + "/chat", json={**body, "message": "Who issues that permit?"}), "(the first run is still finishing)")
            time.sleep(25)
            retry = client.post(SHORT_API + "/chat", json={**body, "message": "Who issues that permit?"})
            show("POST /chat  the same thread after the first run ended", retry, "(no longer 409: the thread accepted the new question, which again outlived the 1 s deadline)")
    finally:
        server.terminate()
        server.wait(timeout=10)


def main() -> None:
    """Run every case against the live API and save the transcript."""
    lines.append("AT-11 API and schemas (real server, real models for the valid chat calls)\n")
    with httpx.Client(timeout=120) as client:
        invalid_requests(client)
        thread_id, interrupt_id = valid_requests(client)
        invalid_resumes(client, thread_id, interrupt_id)
    slow_request()
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
