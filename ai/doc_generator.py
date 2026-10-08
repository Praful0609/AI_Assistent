"""
Documentation generator — creates README and per-module docs using Gemini.
Stores results for later retrieval via the /docs API.
"""
import structlog
from ai.llm_backends import GeminiBackend
from ai.prompts import DOC_GENERATION_PROMPT, README_PROMPT
from parsers.semantic_ir import FileIR
from parsers.static_analysis import AnalysisResult

log = structlog.get_logger()

# Simple in-memory store (replace with DB/file store for production)
_docs_store: dict[str, list[dict]] = {}


def generate_project_docs(
    project_id: str,
    file_irs: list[FileIR],
    analysis: AnalysisResult,
):
    """Generate README + per-module docs and store them."""
    llm = GeminiBackend()
    sections = []

    # ── README ────────────────────────────────────────────────────────────────
    project_summary = _build_project_summary(file_irs, analysis)
    readme = llm.chat(
        messages=[{"role": "user", "content": f"{project_summary}\n\nGenerate a README.md."}],
        system=README_PROMPT,
    )
    sections.append({"title": "README", "content": readme, "type": "readme"})
    log.info("docs.readme_generated", project_id=project_id)

    # ── Module docs ───────────────────────────────────────────────────────────
    # Group files by top-level directory (module)
    modules: dict[str, list[FileIR]] = {}
    for fir in file_irs:
        parts = fir.path.split("/")
        module_name = parts[0] if len(parts) > 1 else "root"
        modules.setdefault(module_name, []).append(fir)

    for module_name, files in list(modules.items())[:10]:  # cap at 10 modules
        module_text = _describe_module(module_name, files)
        doc = llm.chat(
            messages=[{"role": "user", "content": module_text}],
            system=DOC_GENERATION_PROMPT,
        )
        sections.append({"title": module_name, "content": doc, "type": "module"})

    _docs_store[project_id] = sections
    log.info("docs.complete", project_id=project_id, sections=len(sections))

    # Make available to API router
    from app.routers.docs import _docs_cache
    _docs_cache[project_id] = sections


def _build_project_summary(file_irs: list[FileIR], analysis: AnalysisResult) -> str:
    total_classes = sum(len(f.classes) for f in file_irs)
    total_fns = sum(len(f.functions) for f in file_irs)
    langs = {f.language for f in file_irs}
    patterns = [p["pattern"] for p in analysis.design_patterns]

    return (
        f"Languages: {', '.join(langs)}\n"
        f"Files: {len(file_irs)}, Classes: {total_classes}, Functions: {total_fns}\n"
        f"Design patterns detected: {', '.join(set(patterns)) or 'none'}\n"
        f"Dead code candidates: {len(analysis.dead_code)}\n"
        f"Circular dependencies: {len(analysis.circular_deps)}\n"
    )


def _describe_module(module_name: str, files: list[FileIR]) -> str:
    lines = [f"Module: {module_name}"]
    for fir in files[:5]:  # limit per module
        lines.append(f"\nFile: {fir.path}")
        for cls in fir.classes[:3]:
            lines.append(f"  Class: {cls.qualified_name}")
            for m in cls.methods[:5]:
                lines.append(f"    Method: {m.name}({', '.join(p.name for p in m.params)})")
        for fn in fir.functions[:3]:
            lines.append(f"  Function: {fn.name}({', '.join(p.name for p in fn.params)})")
    return "\n".join(lines)
