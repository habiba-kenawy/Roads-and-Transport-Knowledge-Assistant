"""Example requests and responses shown in the generated API docs (/docs). Real values from a run against the indexed documents."""

_DISCLAIMER = "This is not legal advice. The indexed documents are a limited set and may not be complete or current."
_SOURCE = {
    "document_id": "dlp-1432",
    "chunk_id": "dlp-1432-001-44caaf5f",
    "title": "Law No. (13) of 2022 Concerning the Dubai Airports Departure Fee",
    "source_url": "https://dlp.dubai.gov.ae/en/Pages/HTMLViewer.aspx?file=TGF3IE5vLiAoMTMpIG9mIDIwMjIgQ29uY2VybmluZyB0aGUgRHViYWkgQWlycG9ydHMgRGVwYXJ0dXJlIEZlZQ==&year=2022",
    "locator_type": "page",
    "locator": "pp. 1-2",
}

CHAT_REQUEST = {"message": "How much is the departure fee for passengers leaving through Dubai airports?", "search_mode": "hybrid", "top_k": 5}

RESUME_REQUEST = {
    "thread_id": "29dfa395613b41719a3e8fe6aa0a7fb2",
    "interrupt_id": "3b3eb808a25c048027863355970e5931",
    "message": "the departure fee for airport passengers",
}

CHAT_RESPONSES = [
    {
        "thread_id": "40245d307bee40c8b79891ffc2956cf9",
        "status": "answered",
        "answer": "A departure fee of seventy-five dirhams (AED 75.00) will be collected from every passenger departing the United Arab Emirates "
        f"through Dubai airports [1].\n\n{_DISCLAIMER}",
        "citations": [_SOURCE],
        "clarification": None,
        "request_id": "30fa47625337",
    },
    {
        "thread_id": "29dfa395613b41719a3e8fe6aa0a7fb2",
        "status": "needs_clarification",
        "answer": None,
        "citations": [],
        "clarification": {
            "interrupt_id": "3b3eb808a25c048027863355970e5931",
            "question": "What specific violation or law are you asking about regarding the fine?",
        },
        "request_id": "9f2c1a7d4e60",
    },
    {
        "thread_id": "7b1d5c0e92a84f3fb6d1e8a2c4f09a35",
        "status": "insufficient_evidence",
        "answer": "The indexed documents do not contain enough evidence to answer this question. This is not legal advice.",
        "citations": [],
        "clarification": None,
        "request_id": "c41e8d2b7a95",
    },
    {
        "thread_id": "e08a3f6d15c24b79a2f7d6b1c8e35a04",
        "status": "out_of_scope",
        "answer": "I can only help with questions about Dubai Roads and Transport legislation in the indexed documents. This is not legal advice.",
        "citations": [],
        "clarification": None,
        "request_id": "5d7b2a9e1c03",
    },
]

SEARCH_REQUEST = {"query": "departure fee airports", "mode": "hybrid", "top_k": 5}

SEARCH_RESPONSE = {
    "mode": "hybrid",
    "ranking_stage": "reranked",
    "filters_applied": {"year": None, "doc_type": None},
    "results": [
        {
            "rank": 1,
            "score": 10.0,
            "score_type": "llm_relevance_0_10",
            "stage": "reranked",
            "chunk_id": _SOURCE["chunk_id"],
            "doc_id": _SOURCE["document_id"],
            "title": _SOURCE["title"],
            "source_url": _SOURCE["source_url"],
            "locator_type": "page",
            "locator": "pp. 1-2",
            "article": "Article (1)",
            "year": 2022,
            "doc_type": "Law",
            "status": "In Force",
            "text": "Article (1)\na. A departure fee of seventy-five dirhams (AED 75.00) will be collected from every passenger\ndeparting the United Arab Emirates through Dubai airpo...",
        }
    ],
    "candidates_before_rerank": ["dlp-1432-000-82e5035a", "dlp-1432-001-44caaf5f", "dlp-1432-002-f16113aa", "dlp-1432-003-f262e976"],
    "rerank_note": None,
}
