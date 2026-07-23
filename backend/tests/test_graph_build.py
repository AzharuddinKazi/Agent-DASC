from agents.graph import build_graph


def test_graph_builds_without_error():
    graph = build_graph()
    assert "analyzer" in graph.nodes
    assert "finalizer" in graph.nodes
