"""Assemble the full question-answering graph (7.1): understand, route, retrieve, answer."""
from functools import partial
from typing import Callable

from langgraph.graph import END, START, StateGraph

from app.config import Settings
from app.graph.answer import generate_answer
from app.graph.nodes import clarify, plan_query, route_after_plan, scope_response, start_turn
from app.graph.retrieval import build_retrieval_graph
from app.graph.state import GraphState
from app.retrieval.index import SearchIndex


def build_graph(settings: Settings, get_index: Callable[[], SearchIndex], embedder, llm, checkpointer=None):
    """Compile the graph. Models are passed in (or None when not configured), so tests can use fakes."""
    b = StateGraph(GraphState)
    b.add_node("start_turn", start_turn)
    b.add_node("plan_query", partial(plan_query, llm=llm))
    b.add_node("scope_response", scope_response)
    b.add_node("clarify", clarify)
    b.add_node("retrieval", build_retrieval_graph(settings, get_index, embedder, llm))  # the subgraph is one node here
    b.add_node("answer", partial(generate_answer, llm=llm))
    b.add_edge(START, "start_turn")
    b.add_edge("start_turn", "plan_query")
    b.add_conditional_edges("plan_query", route_after_plan, {"scope_response": "scope_response", "clarify": "clarify", "retrieval": "retrieval"})
    b.add_edge("retrieval", "answer")
    b.add_edge("clarify", "plan_query")  # after the user's reply, plan again; route_after_plan caps this loop at 2
    for last in ("answer", "scope_response"):
        b.add_edge(last, END)
    return b.compile(checkpointer=checkpointer)
