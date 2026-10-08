"""
JavaScript/TypeScript Tree-sitter AST extractor.
Handles ES modules, CommonJS, classes, arrow functions.
"""
from tree_sitter import Node
from parsers.semantic_ir import FileIR, ClassIR, FunctionIR, ImportIR, CallIR, ParameterIR
from app.models import Language as LangEnum


def _text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _extract_params(params_node: Node | None, src: bytes) -> list[ParameterIR]:
    if not params_node:
        return []
    params = []
    for child in params_node.named_children:
        if child.type == "identifier":
            params.append(ParameterIR(name=_text(child, src)))
        elif child.type in ("required_parameter", "optional_parameter"):
            name_node = child.child_by_field_name("pattern") or child.named_children[0]
            type_node = child.child_by_field_name("type")
            params.append(ParameterIR(
                name=_text(name_node, src),
                type_hint=_text(type_node, src) if type_node else None,
            ))
        elif child.type == "assignment_pattern":
            # default parameter
            left = child.named_children[0] if child.named_children else None
            if left:
                params.append(ParameterIR(name=_text(left, src)))
    return params


def _collect_calls(node: Node, src: bytes, caller: str, calls: list[CallIR]):
    if node.type == "call_expression":
        func = node.child_by_field_name("function")
        if func:
            calls.append(CallIR(caller=caller, callee=_text(func, src), line=node.start_point[0] + 1))
    for child in node.named_children:
        _collect_calls(child, src, caller, calls)


def _make_function(node: Node, src: bytes, qualifier: str = "") -> FunctionIR:
    name_node = node.child_by_field_name("name")
    name = _text(name_node, src) if name_node else "<anon>"
    qualified = f"{qualifier}.{name}" if qualifier else name

    # Check for async keyword
    is_async = node.type in ("await_expression",) or (
        node.parent and _text(node.parent, src).startswith("async")
    )

    params_node = node.child_by_field_name("parameters") or node.child_by_field_name("formal_parameters")
    return_node = node.child_by_field_name("return_type")

    return FunctionIR(
        name=name,
        qualified_name=qualified,
        params=_extract_params(params_node, src),
        return_type=_text(return_node, src) if return_node else None,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        is_async=is_async,
    )


def extract(root: Node, src: bytes, rel_path: str) -> FileIR:
    lang = LangEnum.TYPESCRIPT if rel_path.endswith((".ts", ".tsx")) else LangEnum.JAVASCRIPT
    file_ir = FileIR(path=rel_path, language=lang.value)

    def walk(node: Node, class_context: str | None = None):
        # ── Import ────────────────────────────────────────────────────────────
        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            module = _text(source_node, src).strip("'\"") if source_node else ""
            symbols = []
            for child in node.named_children:
                if child.type in ("import_clause", "named_imports"):
                    for id_node in child.named_children:
                        if id_node.type == "identifier":
                            symbols.append(_text(id_node, src))
                        elif id_node.type == "import_specifier":
                            name_node = id_node.child_by_field_name("name")
                            if name_node:
                                symbols.append(_text(name_node, src))
            file_ir.imports.append(ImportIR(module=module, symbols=symbols))

        # ── Class ─────────────────────────────────────────────────────────────
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            class_name = _text(name_node, src) if name_node else "<anon>"
            heritage = node.child_by_field_name("class_heritage")
            bases = []
            if heritage:
                for c in heritage.named_children:
                    if c.type == "identifier":
                        bases.append(_text(c, src))

            cls = ClassIR(
                name=class_name,
                qualified_name=class_name,
                bases=bases,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )
            body = node.child_by_field_name("body")
            if body:
                for child in body.named_children:
                    if child.type == "method_definition":
                        fn = _make_function(child, src, qualifier=class_name)
                        cls.methods.append(fn)
                        _collect_calls(child, src, fn.qualified_name, file_ir.calls)
            file_ir.classes.append(cls)

        # ── Function declarations ──────────────────────────────────────────────
        elif node.type in ("function_declaration", "generator_function_declaration"):
            fn = _make_function(node, src, qualifier=class_context or "")
            file_ir.functions.append(fn)
            _collect_calls(node, src, fn.qualified_name, file_ir.calls)

        else:
            for child in node.named_children:
                walk(child, class_context)

    walk(root)
    return file_ir
