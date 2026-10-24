"""Tests for the lightweight code knowledge graph."""
from pathlib import Path

from lt.graph import CodeGraph, build_code_graph


def test_codegraph_builds_nodes_and_edges(tmp_path):
    pkg = tmp_path / "lt"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "models.py").write_text(
        "import json\n"
        "class Model:\n"
        "    def save(self):\n"
        "        pass\n"
        "def helper():\n"
        "    pass\n",
        encoding="utf-8",
    )

    graph = CodeGraph()
    graph.build_from_directory(tmp_path)

    types = {n["type"] for n in graph.nodes}
    assert "module" in types
    assert "class" in types
    assert "function" in types
    assert "method" in types

    define_edges = [e for e in graph.edges if e["relation"] == "defines"]
    assert len(define_edges) == 2  # class Model + function helper


def test_codegraph_skips_pycache(tmp_path):
    src = tmp_path / "lt"
    (src).mkdir()
    (src / "__init__.py").write_text("", encoding="utf-8")
    cache = src / "__pycache__"
    cache.mkdir()
    (cache / "stale.pyc").write_text("garbage", encoding="utf-8")
    (src / "main.py").write_text("x = 1\n", encoding="utf-8")

    graph = CodeGraph()
    graph.build_from_directory(tmp_path)

    module_nodes = [n for n in graph.nodes if n["type"] == "module"]
    assert all("__pycache__" not in n["id"] for n in module_nodes)


def test_codegraph_stats(tmp_path):
    pkg = tmp_path / "lt"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app.py").write_text(
        "class Service:\n"
        "    def run(self):\n"
        "        pass\n"
        "def main():\n"
        "    pass\n",
        encoding="utf-8",
    )

    data = build_code_graph(root=tmp_path)
    stats = data["stats"]
    assert stats["modules"] >= 2
    assert stats["classes"] >= 1
    assert stats["functions"] >= 1
    assert stats["methods"] >= 1
    assert "communities" in data
    assert len(data["nodes"]) > 0


def test_build_code_graph_returns_well_formed(tmp_path):
    pkg = tmp_path / "lt"
    pkg.mkdir()
    (pkg / "mod.py").write_text("import sys\n", encoding="utf-8")

    data = build_code_graph(root=tmp_path)

    assert "nodes" in data
    assert "edges" in data
    assert "stats" in data
    assert "communities" in data

    import_edges = [e for e in data["edges"] if e["relation"] == "imports"]
    assert any(e["target"] == "ext_sys" for e in import_edges)
