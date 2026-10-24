"""Lightweight code knowledge graph for the learning-tools codebase."""
from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeGraph:
    """Build a dependency graph from Python source files."""

    def __init__(self):
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._node_ids: set[str] = set()

    def _add_node(self, node_id: str, label: str, node_type: str, **attrs) -> None:
        if node_id not in self._node_ids:
            self._node_ids.add(node_id)
            self.nodes.append({"id": node_id, "label": label, "type": node_type, **attrs})

    def _add_edge(self, source: str, target: str, relation: str, **attrs) -> None:
        self.edges.append({"source": source, "target": target, "relation": relation, **attrs})

    def build_from_directory(self, root: Path) -> dict[str, Any]:
        """Build graph from all Python files in directory."""
        py_files = sorted(root.rglob("*.py"))

        for f in py_files:
            if "__pycache__" in str(f) or ".venv" in str(f):
                continue
            self._process_file(f, root)

        # Build module-level edges
        self._build_module_edges()

        return {"nodes": self.nodes, "edges": self.edges}

    def _process_file(self, filepath: Path, root: Path) -> None:
        try:
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(filepath))
        except (SyntaxError, UnicodeDecodeError):
            return

        rel_path = filepath.relative_to(root)
        module_name = str(rel_path).replace("\\", "/").replace("/", ".").removesuffix(".py")
        if module_name.endswith(".__init__"):
            module_name = module_name[:-9]

        file_id = f"file_{rel_path.stem}"
        self._add_node(file_id, str(rel_path), "module", path=str(rel_path))

        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._add_edge(file_id, f"ext_{alias.name}", "imports", confidence="EXTRACTED")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._add_edge(file_id, f"ext_{node.module}", "imports_from", confidence="EXTRACTED")

        # Extract classes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                class_id = f"{file_id}_{node.name.lower()}"
                self._add_node(class_id, node.name, "class", file=module_name)
                self._add_edge(file_id, class_id, "defines", confidence="EXTRACTED")

                # Extract methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_id = f"{class_id}_{item.name.lower()}"
                        self._add_node(method_id, item.name, "method", file=module_name)
                        self._add_edge(class_id, method_id, "has_method", confidence="EXTRACTED")

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = f"{file_id}_{node.name.lower()}"
                self._add_node(func_id, node.name, "function", file=module_name)
                self._add_edge(file_id, func_id, "defines", confidence="EXTRACTED")

    def _build_module_edges(self) -> None:
        """Create edges between modules based on shared imports and references."""
        file_nodes = [n for n in self.nodes if n["type"] == "module"]
        for i, f1 in enumerate(file_nodes):
            for f2 in file_nodes[i + 1:]:
                # Check if they share any import targets
                f1_imports = {e["target"] for e in self.edges if e["source"] == f1["id"] and e["relation"].startswith("imports")}
                f2_imports = {e["target"] for e in self.edges if e["source"] == f2["id"] and e["relation"].startswith("imports")}
                shared = f1_imports & f2_imports
                if shared:
                    self._add_edge(f1["id"], f2["id"], "shares_deps", confidence="INFERRED", weight=len(shared))

    def get_communities(self) -> dict[int, list[str]]:
        """Simple community detection based on file prefix."""
        communities: dict[int, list[str]] = {}
        for node in self.nodes:
            if node["type"] == "module":
                path = node.get("path", "")
                if path.startswith("lt/"):
                    cid = 0
                elif path.startswith("tests/"):
                    cid = 1
                elif path.startswith("projects/"):
                    cid = 2
                else:
                    cid = 3
                communities.setdefault(cid, []).append(node["id"])
        return communities

    def get_stats(self) -> dict[str, int]:
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "modules": sum(1 for n in self.nodes if n["type"] == "module"),
            "classes": sum(1 for n in self.nodes if n["type"] == "class"),
            "functions": sum(1 for n in self.nodes if n["type"] == "function"),
            "methods": sum(1 for n in self.nodes if n["type"] == "method"),
        }


def build_code_graph(root: Path | None = None) -> dict[str, Any]:
    """Build and return the code knowledge graph."""
    if root is None:
        root = Path(__file__).resolve().parent.parent

    graph = CodeGraph()
    data = graph.build_from_directory(root)
    data["stats"] = graph.get_stats()
    data["communities"] = {str(k): v for k, v in graph.get_communities().items()}
    return data