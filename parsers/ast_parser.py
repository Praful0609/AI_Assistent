"""
Multi-language AST parser using Tree-sitter.
MVP supports: Python, JavaScript, TypeScript, Java.
"""
import os
from pathlib import Path
from typing import Optional

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from parsers.semantic_ir import (
    FileIR, ClassIR, FunctionIR, ImportIR, CallIR, ParameterIR, ProjectIR
)
from app.models import Language as LangEnum

# ── Build Tree-sitter languages ───────────────────────────────────────────────

PY_LANG   = Language(tspython.language())
JS_LANG   = Language(tsjavascript.language())
TS_LANG   = Language(tstypescript.language_typescript())
TSX_LANG  = Language(tstypescript.language_tsx())
JAVA_LANG = Language(tsjava.language())

_PARSERS: dict[LangEnum, Parser] = {}


def _get_parser(lang: LangEnum) -> Optional[Parser]:
    if lang not in _PARSERS:
        ts_lang = {
            LangEnum.PYTHON: PY_LANG,
            LangEnum.JAVASCRIPT: JS_LANG,
            LangEnum.TYPESCRIPT: TS_LANG,
            LangEnum.JAVA: JAVA_LANG,
        }.get(lang)
        if ts_lang is None:
            return None
        p = Parser(ts_lang)
        _PARSERS[lang] = p
    return _PARSERS[lang]


# ── Language-specific extractors ──────────────────────────────────────────────

def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _extract_python(tree, src: bytes, rel_path: str) -> FileIR:
    """Extract classes, functions, imports, and calls from Python AST."""
    from parsers.languages.python_parser import extract as py_extract
    return py_extract(tree.root_node, src, rel_path)


def _extract_javascript(tree, src: bytes, rel_path: str) -> FileIR:
    from parsers.languages.javascript_parser import extract as js_extract
    return js_extract(tree.root_node, src, rel_path)


def _extract_java(tree, src: bytes, rel_path: str) -> FileIR:
    from parsers.languages.java_parser import extract as java_extract
    return java_extract(tree.root_node, src, rel_path)


_EXTRACTORS = {
    LangEnum.PYTHON: _extract_python,
    LangEnum.JAVASCRIPT: _extract_javascript,
    LangEnum.TYPESCRIPT: _extract_javascript,  # same extractor, JS-compatible TS
    LangEnum.JAVA: _extract_java,
}


def parse_file(abs_path: str, rel_path: str, lang: LangEnum) -> FileIR:
    """Parse a single source file and return its FileIR."""
    parser = _get_parser(lang)
    if parser is None:
        return FileIR(path=rel_path, language=lang.value, parse_error="Unsupported language")

    try:
        src = Path(abs_path).read_bytes()
        tree = parser.parse(src)
        extractor = _EXTRACTORS.get(lang)
        if extractor is None:
            return FileIR(path=rel_path, language=lang.value, parse_error="No extractor")

        file_ir = extractor(tree, src, rel_path)
        file_ir.raw_content = src.decode("utf-8", errors="replace")
        file_ir.line_count = src.count(b"\n") + 1
        return file_ir

    except Exception as e:
        return FileIR(
            path=rel_path,
            language=lang.value,
            parse_error=str(e),
        )


def parse_project(source_dir: str, file_map: dict[str, LangEnum]) -> list[FileIR]:
    """
    Parse all supported files in the project.
    Returns list of FileIR (one per parsed file).
    """
    PARSEABLE = {LangEnum.PYTHON, LangEnum.JAVASCRIPT, LangEnum.TYPESCRIPT, LangEnum.JAVA}
    results = []

    for rel_path, lang in file_map.items():
        if lang not in PARSEABLE:
            continue
        abs_path = os.path.join(source_dir, rel_path)
        if not os.path.isfile(abs_path):
            continue
        file_ir = parse_file(abs_path, rel_path, lang)
        results.append(file_ir)

    return results
