"""
Neo4j knowledge graph builder.
Converts Semantic IR + Analysis results into graph nodes and relationships.
"""
import structlog
from neo4j import GraphDatabase, Driver
from app.config import settings
from parsers.semantic_ir import FileIR
from parsers.static_analysis import AnalysisResult

log = structlog.get_logger()

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


def build_graph(project_id: str, file_irs: list[FileIR], analysis: AnalysisResult):
    """
    Build the knowledge graph for a project in Neo4j.
    Creates nodes for Files, Classes, Functions, Modules
    and relationships: CONTAINS, HAS_METHOD, CALLS, IMPORTS, INHERITS_FROM.
    """
    driver = get_driver()
    with driver.session() as session:
        # Clear existing graph for this project (re-analysis)
        session.run("MATCH (n {project_id: $pid}) DETACH DELETE n", pid=project_id)

        for fir in file_irs:
            _ingest_file(session, project_id, fir)

        # Cross-file CALLS relationships
        _ingest_calls(session, project_id, analysis)

        # Design patterns
        _ingest_patterns(session, project_id, analysis)

    log.info("neo4j.graph_built", project_id=project_id)


def _ingest_file(session, project_id: str, fir: FileIR):
    # File node
    session.run("""
        MERGE (f:File {project_id: $pid, path: $path})
        SET f.language = $lang
    """, pid=project_id, path=fir.path, lang=fir.language)

    for cls in fir.classes:
        # Class node
        session.run("""
            MERGE (c:Class {project_id: $pid, qualified_name: $qn})
            SET c.name = $name, c.file_path = $path, c.docstring = $doc
        """, pid=project_id, qn=cls.qualified_name, name=cls.name,
             path=fir.path, doc=cls.docstring or "")

        # File CONTAINS Class
        session.run("""
            MATCH (f:File {project_id: $pid, path: $path})
            MATCH (c:Class {project_id: $pid, qualified_name: $qn})
            MERGE (f)-[:CONTAINS]->(c)
        """, pid=project_id, path=fir.path, qn=cls.qualified_name)

        # Inheritance
        for base in cls.bases:
            session.run("""
                MERGE (b:Class {project_id: $pid, name: $base})
                WITH b
                MATCH (c:Class {project_id: $pid, qualified_name: $qn})
                MERGE (c)-[:INHERITS_FROM]->(b)
            """, pid=project_id, base=base, qn=cls.qualified_name)

        for method in cls.methods:
            _ingest_function(session, project_id, fir.path, method, parent_class=cls.qualified_name)

    for fn in fir.functions:
        _ingest_function(session, project_id, fir.path, fn, parent_class=None)

    for imp in fir.imports:
        session.run("""
            MERGE (m:Module {project_id: $pid, name: $mod})
            WITH m
            MATCH (f:File {project_id: $pid, path: $path})
            MERGE (f)-[:IMPORTS]->(m)
        """, pid=project_id, mod=imp.module, path=fir.path)


def _ingest_function(session, project_id: str, file_path: str, fn, parent_class: str | None):
    session.run("""
        MERGE (fn:Function {project_id: $pid, qualified_name: $qn})
        SET fn.name = $name, fn.file_path = $path,
            fn.start_line = $sl, fn.end_line = $el,
            fn.docstring = $doc, fn.is_async = $async
    """, pid=project_id, qn=fn.qualified_name, name=fn.name,
         path=file_path, sl=fn.start_line, el=fn.end_line,
         doc=fn.docstring or "", async_=fn.is_async)

    if parent_class:
        session.run("""
            MATCH (c:Class {project_id: $pid, qualified_name: $cqn})
            MATCH (fn:Function {project_id: $pid, qualified_name: $fqn})
            MERGE (c)-[:HAS_METHOD]->(fn)
        """, pid=project_id, cqn=parent_class, fqn=fn.qualified_name)
    else:
        session.run("""
            MATCH (f:File {project_id: $pid, path: $path})
            MATCH (fn:Function {project_id: $pid, qualified_name: $fqn})
            MERGE (f)-[:CONTAINS]->(fn)
        """, pid=project_id, path=file_path, fqn=fn.qualified_name)


def _ingest_calls(session, project_id: str, analysis: AnalysisResult):
    for caller, callees in analysis.call_graph.items():
        for callee in callees:
            session.run("""
                MERGE (caller:Function {project_id: $pid, qualified_name: $caller})
                MERGE (callee:Function {project_id: $pid, qualified_name: $callee})
                MERGE (caller)-[:CALLS]->(callee)
            """, pid=project_id, caller=caller, callee=callee)


def _ingest_patterns(session, project_id: str, analysis: AnalysisResult):
    for p in analysis.design_patterns:
        session.run("""
            MERGE (pat:Pattern {project_id: $pid, type: $ptype})
            WITH pat
            MATCH (c:Class {project_id: $pid, qualified_name: $cqn})
            MERGE (c)-[:IMPLEMENTS]->(pat)
        """, pid=project_id, ptype=p["pattern"], cqn=p["class"])
