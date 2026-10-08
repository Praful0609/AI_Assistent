"""
Language detection for source files.
Uses file extension + shebang heuristics (no external process needed).
Also handles Git clone via gitpython.
"""
import os
import re
from pathlib import Path
from app.models import Language

# ── Extension → Language map ──────────────────────────────────────────────────
EXTENSION_MAP: dict[str, Language] = {
    # Python
    ".py": Language.PYTHON, ".pyw": Language.PYTHON, ".pyi": Language.PYTHON,
    # JavaScript
    ".js": Language.JAVASCRIPT, ".mjs": Language.JAVASCRIPT, ".cjs": Language.JAVASCRIPT,
    # TypeScript
    ".ts": Language.TYPESCRIPT, ".tsx": Language.TYPESCRIPT,
    ".jsx": Language.JAVASCRIPT,
    # Java
    ".java": Language.JAVA,
    # Go
    ".go": Language.GO,
    # Rust
    ".rs": Language.RUST,
    # C / C++
    ".c": Language.CPP, ".cpp": Language.CPP, ".cc": Language.CPP,
    ".cxx": Language.CPP, ".h": Language.CPP, ".hpp": Language.CPP,
    # C#
    ".cs": Language.CSHARP,
    # Ruby
    ".rb": Language.RUBY,
}

# Files/dirs to skip
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__",
    ".venv", "venv", "env", ".env", "dist", "build",
    "target", "bin", "obj", ".idea", ".vscode",
}
IGNORE_EXTENSIONS = {".min.js", ".bundle.js", ".map", ".lock", ".sum"}

# Supported languages for AST parsing (MVP)
PARSEABLE_LANGUAGES = {Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT, Language.JAVA}


def clone_or_prepare(source_type: str, source_value: str, project_dir: str) -> str:
    """
    Return the path to the source directory.
    - For git_url: clone into project_dir/src
    - For zip: source_value is already the extracted path
    """
    if source_type == "git_url":
        import git
        src_dir = os.path.join(project_dir, "src")
        os.makedirs(src_dir, exist_ok=True)
        git.Repo.clone_from(source_value, src_dir, depth=1)
        return src_dir
    else:
        # ZIP already extracted; source_value IS the src directory
        return source_value


def detect_languages(source_dir: str) -> dict[str, Language]:
    """
    Walk source_dir and return {relative_path: Language} for all source files.
    Skips ignored dirs and non-source extensions.
    """
    result: dict[str, Language] = {}
    source_path = Path(source_dir)

    for root, dirs, files in os.walk(source_dir):
        # Prune ignored directories in-place
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

        for fname in files:
            fpath = Path(root) / fname
            rel = str(fpath.relative_to(source_path))

            # Skip binary / lock / minified
            suffix = fpath.suffix.lower()
            if any(rel.endswith(ext) for ext in IGNORE_EXTENSIONS):
                continue

            lang = EXTENSION_MAP.get(suffix, Language.UNKNOWN)

            # Shebang fallback for extensionless scripts
            if lang == Language.UNKNOWN and not suffix:
                try:
                    with open(fpath, "rb") as f:
                        first_line = f.readline(128).decode("utf-8", errors="ignore")
                    if "python" in first_line:
                        lang = Language.PYTHON
                    elif "node" in first_line or "bash" in first_line:
                        lang = Language.JAVASCRIPT
                except OSError:
                    continue

            result[rel] = lang

    return result
