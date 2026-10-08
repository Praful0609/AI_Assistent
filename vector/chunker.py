"""
Chunk Semantic IR into embeddable units.
Each chunk has: id, text, metadata (type, name, file, language).
"""
import hashlib
from dataclasses import dataclass
from parsers.semantic_ir import FileIR, FunctionIR, ClassIR


@dataclass
class Chunk:
    id: str
    text: str
    chunk_type: str    # "function" | "class" | "file"
    name: str
    file_path: str
    language: str
    project_id: str
    start_line: int = 0
    end_line: int = 0


def _make_id(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _function_text(fn: FunctionIR) -> str:
    lines = [f"Function: {fn.qualified_name}"]
    if fn.params:
        params_str = ", ".join(
            f"{p.name}: {p.type_hint}" if p.type_hint else p.name
            for p in fn.params
        )
        lines.append(f"Parameters: ({params_str})")
    if fn.return_type:
        lines.append(f"Returns: {fn.return_type}")
    if fn.docstring:
        lines.append(f"Docstring: {fn.docstring[:400]}")
    return "\n".join(lines)


def _class_text(cls: ClassIR) -> str:
    lines = [f"Class: {cls.qualified_name}"]
    if cls.bases:
        lines.append(f"Inherits: {', '.join(cls.bases)}")
    if cls.docstring:
        lines.append(f"Docstring: {cls.docstring[:400]}")
    method_names = [m.name for m in cls.methods]
    if method_names:
        lines.append(f"Methods: {', '.join(method_names)}")
    return "\n".join(lines)


def chunk_semantic_ir(project_id: str, file_irs: list[FileIR]) -> list[Chunk]:
    """
    Convert FileIR list into a flat list of embeddable Chunks.
    Strategy: one chunk per function, one per class, one per file (summary).
    """
    chunks: list[Chunk] = []

    for fir in file_irs:
        # Per-class chunk
        for cls in fir.classes:
            text = _class_text(cls)
            chunks.append(Chunk(
                id=_make_id(project_id, fir.path, "class", cls.qualified_name),
                text=text,
                chunk_type="class",
                name=cls.qualified_name,
                file_path=fir.path,
                language=fir.language,
                project_id=project_id,
                start_line=cls.start_line,
                end_line=cls.end_line,
            ))
            # Per-method chunk
            for method in cls.methods:
                text = _function_text(method)
                chunks.append(Chunk(
                    id=_make_id(project_id, fir.path, "function", method.qualified_name),
                    text=text,
                    chunk_type="function",
                    name=method.qualified_name,
                    file_path=fir.path,
                    language=fir.language,
                    project_id=project_id,
                    start_line=method.start_line,
                    end_line=method.end_line,
                ))

        # Per top-level function
        for fn in fir.functions:
            text = _function_text(fn)
            chunks.append(Chunk(
                id=_make_id(project_id, fir.path, "function", fn.qualified_name),
                text=text,
                chunk_type="function",
                name=fn.qualified_name,
                file_path=fir.path,
                language=fir.language,
                project_id=project_id,
                start_line=fn.start_line,
                end_line=fn.end_line,
            ))

        # File-level summary chunk (first 2000 chars of raw content)
        if fir.raw_content:
            summary = fir.raw_content[:2000]
            chunks.append(Chunk(
                id=_make_id(project_id, fir.path, "file"),
                text=f"File: {fir.path}\n\n{summary}",
                chunk_type="file",
                name=fir.path,
                file_path=fir.path,
                language=fir.language,
                project_id=project_id,
            ))

    return chunks
