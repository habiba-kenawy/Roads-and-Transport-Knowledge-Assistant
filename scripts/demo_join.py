"""Walkthrough demo (7.2): why the join must be the list form add_edge([a, b], join).

Branch A takes 1 step, branch B takes 2 steps. With plain edges the join runs TWICE (once too early); with the
list-form join it runs ONCE, after both branches finished. Run: python -m scripts.demo_join
"""
import time
from typing_extensions import TypedDict
from langgraph.graph import END, START, StateGraph

class S(TypedDict, total=False):
    a: str; b: str; c: str; b2: str

runs = []
def mk(name, secs, key):
    def n(s):
        time.sleep(secs); runs.append(name); return {key: name}
    return n
def join(s):
    runs.append("JOIN(has a=%s b=%s)" % (s.get("a"), s.get("b"))); return {"c": "x"}

def build(kind):
    g = StateGraph(S)
    g.add_node("A", mk("A", 0.1, "a")); g.add_node("B", mk("B", 0.3, "b")); g.add_node("B2", mk("B2", 0.1, "b2")); g.add_node("J", join)
    g.add_edge(START, "A")
    if kind == "equal_plain":        # both branches 1 step, two plain edges
        g.add_edge(START, "B"); g.add_edge("A", "J"); g.add_edge("B", "J")
    elif kind == "equal_list":       # both branches 1 step, list-form join
        g.add_edge(START, "B"); g.add_edge(["A", "B"], "J")
    elif kind == "unequal_plain":    # branch B has 2 steps (B then B2); two plain edges
        g.add_edge(START, "B"); g.add_edge("B", "B2"); g.add_edge("A", "J"); g.add_edge("B2", "J")
    elif kind == "unequal_list":     # branch B has 2 steps; list-form join
        g.add_edge(START, "B"); g.add_edge("B", "B2"); g.add_edge(["A", "B2"], "J")
    g.add_edge("J", END)
    return g.compile()

for kind in ("equal_plain", "equal_list", "unequal_plain", "unequal_list"):
    runs.clear(); build(kind).invoke({})
    print(f"{kind:<14} -> {runs}   join ran {sum(r.startswith('JOIN') for r in runs)}x")
