"""Assemble LLM context from vector chunks + graph expansion."""


def assemble_context(question: str, chunks: list[dict], graph_nodes: list[dict]) -> str:
    """
    Build a structured prompt context combining:
    - The user question
    - Top-k vector search code chunks
    - 1-hop graph neighbours for richer relationship context
    """
    parts = [f"## Developer Question\n{question}\n"]

    if chunks:
        parts.append("## Relevant Code Chunks (from vector search)")
        for i, chunk in enumerate(chunks[:8], 1):
            parts.append(
                f"\n### [{i}] {chunk.get('type', '').upper()}: `{chunk.get('name', '')}`"
                f"\n**File:** `{chunk.get('file_path', '')}`  "
                f"**Language:** {chunk.get('language', '')}\n"
                f"```\n{chunk.get('text', '')[:600]}\n```"
            )

    if graph_nodes:
        parts.append("\n## Knowledge Graph Context (relationships)")
        for node in graph_nodes[:10]:
            neighbours_str = ", ".join(
                f"{n['type']} `{n['name']}` ({n['rel']})"
                for n in (node.get("neighbours") or [])[:5]
                if n.get("name")
            )
            parts.append(
                f"- **{node.get('type')} `{node.get('entity')}`** → {neighbours_str or 'no graph neighbours'}"
            )

    parts.append(
        "\n---\nUsing the code chunks and graph relationships above, "
        "answer the developer question accurately. "
        "Cite specific file paths and function names in your answer."
    )

    return "\n".join(parts)
