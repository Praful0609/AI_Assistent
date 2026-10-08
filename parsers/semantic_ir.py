"""
Semantic Intermediate Representation (IR) dataclasses.
Output of the AST parser; input to graph builder, vector indexer, and AI.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParameterIR:
    name: str
    type_hint: Optional[str] = None
    default: Optional[str] = None


@dataclass
class FunctionIR:
    name: str
    qualified_name: str          # e.g. "AuthService.login"
    params: list[ParameterIR] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    decorators: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0
    is_async: bool = False
    is_static: bool = False
    body_summary: str = ""       # first 500 chars of body text


@dataclass
class ClassIR:
    name: str
    qualified_name: str
    bases: list[str] = field(default_factory=list)
    methods: list[FunctionIR] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    docstring: Optional[str] = None
    decorators: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0


@dataclass
class ImportIR:
    module: str
    symbols: list[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_relative: bool = False


@dataclass
class CallIR:
    caller: str         # qualified name of calling function
    callee: str         # qualified name or best-effort name of called function
    line: int = 0


@dataclass
class FileIR:
    """Complete semantic IR for one source file."""
    path: str                    # relative path within project
    language: str
    classes: list[ClassIR] = field(default_factory=list)
    functions: list[FunctionIR] = field(default_factory=list)
    imports: list[ImportIR] = field(default_factory=list)
    calls: list[CallIR] = field(default_factory=list)
    raw_content: str = ""        # full source text (for embedding)
    line_count: int = 0
    parse_error: Optional[str] = None  # set if parsing failed


@dataclass
class ProjectIR:
    """Collection of all file IRs for a project."""
    project_id: str
    files: list[FileIR] = field(default_factory=list)

    @property
    def all_classes(self) -> list[ClassIR]:
        return [cls for f in self.files for cls in f.classes]

    @property
    def all_functions(self) -> list[FunctionIR]:
        return [fn for f in self.files for fn in f.functions] + \
               [m for f in self.files for cls in f.classes for m in cls.methods]

    @property
    def all_calls(self) -> list[CallIR]:
        return [c for f in self.files for c in f.calls]
