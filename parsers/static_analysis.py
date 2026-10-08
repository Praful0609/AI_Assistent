"""
Static analysis passes over the Semantic IR.
Produces: call graph, dependency graph, dead code, coupling, design patterns.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from parsers.semantic_ir import ProjectIR, FileIR, FunctionIR


@dataclass
class AnalysisResult:
    call_graph: dict[str, list[str]] = field(default_factory=dict)     # caller -> [callees]
    dep_graph: dict[str, list[str]] = field(default_factory=dict)       # file -> [imported modules]
    dead_code: list[dict] = field(default_factory=list)                  # unreachable functions/classes
    circular_deps: list[list[str]] = field(default_factory=list)
    coupling_metrics: list[dict] = field(default_factory=list)
    design_patterns: list[dict] = field(default_factory=list)


def run_analysis(file_irs: list[FileIR]) -> AnalysisResult:
    result = AnalysisResult()
    _build_call_graph(file_irs, result)
    _build_dep_graph(file_irs, result)
    _detect_dead_code(file_irs, result)
    _detect_circular_deps(result)
    _compute_coupling(file_irs, result)
    _detect_patterns(file_irs, result)
    return result


def _build_call_graph(file_irs: list[FileIR], result: AnalysisResult):
    """Build caller → [callees] map from all FileIR call lists."""
    graph: dict[str, set[str]] = defaultdict(set)
    for fir in file_irs:
        for call in fir.calls:
            graph[call.caller].add(call.callee)
    result.call_graph = {k: list(v) for k, v in graph.items()}


def _build_dep_graph(file_irs: list[FileIR], result: AnalysisResult):
    """Build file → [imported module names]."""
    for fir in file_irs:
        result.dep_graph[fir.path] = [imp.module for imp in fir.imports]


def _detect_dead_code(file_irs: list[FileIR], result: AnalysisResult):
    """
    Detect functions never appear as a callee in the call graph.
    Heuristic: if a function's qualified name is never called, flag it.
    """
    all_callees: set[str] = set()
    for callees in result.call_graph.values():
        all_callees.update(callees)

    for fir in file_irs:
        all_fns = list(fir.functions)
        for cls in fir.classes:
            all_fns.extend(cls.methods)
        for fn in all_fns:
            # Public functions never called → potential dead code
            if (
                not fn.name.startswith("_")           # skip private
                and fn.name not in ("__init__", "main", "setUp", "tearDown")
                and fn.qualified_name not in all_callees
                and fn.name not in all_callees
            ):
                result.dead_code.append({
                    "type": "function",
                    "name": fn.qualified_name,
                    "file": fir.path,
                    "line": fn.start_line,
                })


def _detect_circular_deps(result: AnalysisResult):
    """Detect cycles in the dependency graph using DFS."""
    graph = result.dep_graph
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]):
        visited.add(node)
        rec_stack.add(node)
        for neighbour in graph.get(node, []):
            if neighbour not in graph:
                continue  # external module
            if neighbour not in visited:
                dfs(neighbour, path + [neighbour])
            elif neighbour in rec_stack:
                cycle_start = path.index(neighbour) if neighbour in path else 0
                cycles.append(path[cycle_start:] + [neighbour])

        rec_stack.discard(node)

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node, [node])

    result.circular_deps = cycles


def _compute_coupling(file_irs: list[FileIR], result: AnalysisResult):
    """Compute afferent (Ca) and efferent (Ce) coupling per file."""
    afferent: dict[str, int] = defaultdict(int)   # who depends ON this file
    efferent: dict[str, int] = defaultdict(int)   # how many others this file depends ON

    for fir in file_irs:
        efferent[fir.path] = len(fir.imports)
        for imp in fir.imports:
            afferent[imp.module] += 1

    for fir in file_irs:
        ca = afferent.get(fir.path, 0)
        ce = efferent.get(fir.path, 0)
        instability = ce / (ca + ce) if (ca + ce) > 0 else 0
        result.coupling_metrics.append({
            "file": fir.path,
            "afferent": ca,
            "efferent": ce,
            "instability": round(instability, 3),
        })


def _detect_patterns(file_irs: list[FileIR], result: AnalysisResult):
    """Heuristic design pattern detection."""
    for fir in file_irs:
        for cls in fir.classes:
            method_names = {m.name for m in cls.methods}

            # Singleton: has _instance field + getInstance method
            if "get_instance" in method_names or "getInstance" in method_names:
                if "_instance" in cls.fields or "__instance" in cls.fields:
                    result.design_patterns.append({
                        "pattern": "Singleton",
                        "class": cls.qualified_name,
                        "file": fir.path,
                    })

            # Observer: has subscribe/notify methods
            if {"subscribe", "notify"}.issubset(method_names) or \
               {"add_listener", "notify_listeners"}.issubset(method_names):
                result.design_patterns.append({
                    "pattern": "Observer",
                    "class": cls.qualified_name,
                    "file": fir.path,
                })

            # Factory: class name contains "Factory" or has create() method
            if "Factory" in cls.name or "factory" in cls.name.lower():
                result.design_patterns.append({
                    "pattern": "Factory",
                    "class": cls.qualified_name,
                    "file": fir.path,
                })
