"""
Diagram generator — converts Neo4j graph data into Mermaid syntax.
Supports: class, sequence, dependency, module diagrams.
"""
from graph.neo4j_builder import get_driver
import structlog

log = structlog.get_logger()


def generate_diagram(project_id: str, diagram_type: str) -> tuple[str, str]:
    """
    Returns (content, format) where format is 'mermaid' or 'json'.
    """
    generators = {
        "class":      _class_diagram,
        "dependency": _dependency_diagram,
        "module":     _module_diagram,
        "sequence":   _sequence_diagram,
    }
    fn = generators.get(diagram_type)
    if fn is None:
        return "# Unsupported diagram type", "mermaid"
    return fn(project_id)


def _class_diagram(project_id: str) -> tuple[str, str]:
    """Mermaid classDiagram from Neo4j Class/INHERITS_FROM data."""
    driver = get_driver()
    lines = ["classDiagram"]

    with driver.session() as session:
        # Classes and methods
        result = session.run("""
            MATCH (c:Class {project_id: $pid})
            OPTIONAL MATCH (c)-[:HAS_METHOD]->(m:Function)
            RETURN c.name AS cls, collect(m.name) AS methods
            LIMIT 30
        """, pid=project_id)
        for record in result:
            cls = record["cls"]
            lines.append(f"  class {_safe_name(cls)} {{")
            for method in record["methods"][:8]:  # cap methods shown
                lines.append(f"    +{method}()")
            lines.append("  }")

        # Inheritance
        result = session.run("""
            MATCH (c:Class {project_id: $pid})-[:INHERITS_FROM]->(b:Class)
            RETURN c.name AS child, b.name AS parent
            LIMIT 30
        """, pid=project_id)
        for record in result:
            lines.append(f"  {_safe_name(record['parent'])} <|-- {_safe_name(record['child'])}")

    return "\n".join(lines), "mermaid"


def _dependency_diagram(project_id: str) -> tuple[str, str]:
    """Mermaid flowchart of file import dependencies."""
    driver = get_driver()
    lines = ["flowchart LR"]

    with driver.session() as session:
        result = session.run("""
            MATCH (f:File {project_id: $pid})-[:IMPORTS]->(m:Module {project_id: $pid})
            RETURN f.path AS file, m.name AS module
            LIMIT 50
        """, pid=project_id)
        seen = set()
        for record in result:
            f = _safe_name(record["file"].split("/")[-1])
            m = _safe_name(record["module"])
            key = (f, m)
            if key not in seen:
                seen.add(key)
                lines.append(f"  {f} --> {m}")

    return "\n".join(lines), "mermaid"


def _module_diagram(project_id: str) -> tuple[str, str]:
    """Mermaid flowchart of top-level module structure."""
    driver = get_driver()
    lines = ["flowchart TD"]

    with driver.session() as session:
        result = session.run("""
            MATCH (f:File {project_id: $pid})
            RETURN f.path AS path, f.language AS lang
            LIMIT 80
        """, pid=project_id)
        modules: dict[str, list[str]] = {}
        for record in result:
            parts = record["path"].split("/")
            module = parts[0] if len(parts) > 1 else "root"
            fname = parts[-1]
            modules.setdefault(module, []).append(fname)

        for module, files in modules.items():
            safe_mod = _safe_name(module)
            lines.append(f"  subgraph {safe_mod}")
            for f in files[:6]:
                lines.append(f"    {_safe_name(f)}[{f}]")
            lines.append("  end")

    return "\n".join(lines), "mermaid"


def _sequence_diagram(project_id: str) -> tuple[str, str]:
    """Mermaid sequenceDiagram from top-level CALLS relationships."""
    driver = get_driver()
    lines = ["sequenceDiagram"]

    with driver.session() as session:
        result = session.run("""
            MATCH (caller:Function {project_id: $pid})-[:CALLS]->(callee:Function {project_id: $pid})
            RETURN caller.name AS from, callee.name AS to
            LIMIT 30
        """, pid=project_id)
        for record in result:
            lines.append(f"  {_safe_name(record['from'])}->>+{_safe_name(record['to'])}: call")

    return "\n".join(lines), "mermaid"


def _safe_name(s: str) -> str:
    """Sanitize node names for Mermaid (remove special chars)."""
    return s.replace(".", "_").replace("/", "_").replace("-", "_").replace(" ", "_")
