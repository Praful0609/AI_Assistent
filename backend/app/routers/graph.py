"""Graph explorer API — serves Neo4j data to the frontend."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any
from graph.neo4j_builder import get_driver
from app.config import settings

router = APIRouter(prefix="/projects/{project_id}/graph", tags=["graph"])


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: dict[str, Any]


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_nodes: int
    total_edges: int


@router.get("", response_model=GraphResponse)
def get_project_graph(
    project_id: str,
    node_types: list[str] = Query(default=["Class", "Function", "File"]),
    limit: int = Query(default=200, le=1000),
):
    """Return graph nodes and edges for visualization."""
    driver = get_driver()
    with driver.session() as session:
        # Fetch nodes
        node_query = """
        MATCH (n)
        WHERE n.project_id = $project_id
          AND any(label IN labels(n) WHERE label IN $node_types)
        RETURN id(n) AS id, labels(n)[0] AS type, properties(n) AS props
        LIMIT $limit
        """
        nodes_result = session.run(node_query, project_id=project_id, node_types=node_types, limit=limit)
        nodes = [
            GraphNode(
                id=str(r["id"]),
                label=r["props"].get("name", str(r["id"])),
                type=r["type"],
                properties=dict(r["props"]),
            )
            for r in nodes_result
        ]

        # Fetch edges between returned node IDs
        node_ids = [n.id for n in nodes]
        edge_query = """
        MATCH (a)-[r]->(b)
        WHERE toString(id(a)) IN $node_ids AND toString(id(b)) IN $node_ids
        RETURN toString(id(a)) AS source, toString(id(b)) AS target, type(r) AS type
        """
        edges_result = session.run(edge_query, node_ids=node_ids)
        edges = [
            GraphEdge(source=r["source"], target=r["target"], type=r["type"])
            for r in edges_result
        ]

    return GraphResponse(
        nodes=nodes,
        edges=edges,
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


@router.get("/neighbours/{node_id}")
def get_node_neighbours(project_id: str, node_id: str, depth: int = Query(default=1, le=3)):
    """Expand neighbours of a specific graph node up to N hops."""
    driver = get_driver()
    with driver.session() as session:
        query = f"""
        MATCH path = (start)-[*1..{depth}]-(neighbour)
        WHERE id(start) = toInteger($node_id) AND start.project_id = $project_id
        RETURN nodes(path) AS ns, relationships(path) AS rels
        LIMIT 100
        """
        result = session.run(query, node_id=node_id, project_id=project_id)
        nodes, edges = [], []
        seen_nodes, seen_edges = set(), set()
        for record in result:
            for n in record["ns"]:
                if n.id not in seen_nodes:
                    seen_nodes.add(n.id)
                    nodes.append({"id": str(n.id), "type": list(n.labels)[0], "properties": dict(n)})
            for r in record["rels"]:
                key = (r.start_node.id, r.end_node.id, r.type)
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({"source": str(r.start_node.id), "target": str(r.end_node.id), "type": r.type})

    return {"nodes": nodes, "edges": edges}
