"""The reusable retrieval subgraph: route by mode; hybrid runs lexical and semantic in PARALLEL, joins, fuses, reranks (7.1)."""
from functools import partial
from typing import Callable

from langgraph.graph import END, START, StateGraph

from app.config import Settings
from app.errors import ModelNotConfiguredError
from app.graph.state import GraphState
from app.graph.tracing import traced
from app.retrieval.fusion import rrf_fuse
from app.retrieval.index import SearchIndex, lexical_search
from app.retrieval.rerank import rerank
from app.retrieval.search import checked_semantic_search


def need_embedder(embedder):
    """Fail clearly when semantic search is requested but no embedding model is configured."""
    if embedder is None:
        raise ModelNotConfiguredError("embedding model is not configured (check .env)")
    return embedder


@traced("lexical_node")
def lexical_node(state: GraphState, *, get_index: Callable[[], SearchIndex], candidates: int) -> dict:
    """Hybrid branch 1: BM25 candidates, written to its OWN key."""
    return {"lexical_candidates": lexical_search(get_index(), state["standalone_query"], state["effective_filters"], candidates)}


@traced("semantic_node")
def semantic_node(state: GraphState, *, get_index: Callable[[], SearchIndex], embedder, candidates: int) -> dict:
    """Hybrid branch 2: embedding candidates, written to its OWN key."""
    hits = checked_semantic_search(get_index(), need_embedder(embedder), state["standalone_query"], state["effective_filters"], candidates)
    return {"semantic_candidates": hits}


@traced("fuse_node")
def fuse_node(state: GraphState, *, candidates: int) -> dict:
    """The join: runs once, only after BOTH branches finished; merges and deduplicates with RRF."""
    return {"fused": rrf_fuse([state["lexical_candidates"], state["semantic_candidates"]], top_n=candidates)}


@traced("rerank_node")
def rerank_node(state: GraphState, *, llm) -> dict:
    """Separate reranking stage over the fused candidates; falls back to the fused order if the model is unavailable."""
    fused, top_k = state["fused"], state["top_k"]
    if llm is None:
        final, note = fused[:top_k], "reranking unavailable (chat model not configured); fused order returned"
    else:
        final, note = rerank(llm, state["standalone_query"], fused, top_k)
    return {"evidence": final, "rerank_note": note, "ranking_stage": final[0].stage if final else "reranked"}


@traced("lexical_only")
def lexical_only(state: GraphState, *, get_index: Callable[[], SearchIndex]) -> dict:
    """Lexical mode: BM25 results are the final evidence."""
    hits = lexical_search(get_index(), state["standalone_query"], state["effective_filters"], state["top_k"])
    return {"evidence": hits, "ranking_stage": "lexical"}


@traced("semantic_only")
def semantic_only(state: GraphState, *, get_index: Callable[[], SearchIndex], embedder) -> dict:
    """Semantic mode: embedding results are the final evidence."""
    hits = checked_semantic_search(get_index(), need_embedder(embedder), state["standalone_query"], state["effective_filters"], state["top_k"])
    return {"evidence": hits, "ranking_stage": "semantic"}


def route_mode(state: GraphState) -> list[str]:
    """Conditional entry: one branch for lexical or semantic, two PARALLEL branches for hybrid."""
    return {"lexical": ["lexical_only"], "semantic": ["semantic_only"], "hybrid": ["lexical_node", "semantic_node"]}[state["search_mode"]]


def build_retrieval_graph(settings: Settings, get_index: Callable[[], SearchIndex], embedder, llm):
    """Compile the retrieval subgraph; it shares its state keys with the parent graph, so it plugs in as one node."""
    n = settings.retrieval_candidates
    b = StateGraph(GraphState)
    b.add_node("lexical_only", partial(lexical_only, get_index=get_index))
    b.add_node("semantic_only", partial(semantic_only, get_index=get_index, embedder=embedder))
    b.add_node("lexical_node", partial(lexical_node, get_index=get_index, candidates=n))
    b.add_node("semantic_node", partial(semantic_node, get_index=get_index, embedder=embedder, candidates=n))
    b.add_node("fuse_node", partial(fuse_node, candidates=n))
    b.add_node("rerank_node", partial(rerank_node, llm=llm))
    b.add_conditional_edges(START, route_mode, ["lexical_only", "semantic_only", "lexical_node", "semantic_node"])
    b.add_edge(["lexical_node", "semantic_node"], "fuse_node")  # waits for BOTH branches
    b.add_edge("fuse_node", "rerank_node")
    for last in ("lexical_only", "semantic_only", "rerank_node"):
        b.add_edge(last, END)
    return b.compile()
