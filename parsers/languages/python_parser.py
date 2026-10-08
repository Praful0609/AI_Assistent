"""Python-specific Tree-sitter AST extractor."""
from tree_sitter import Node
from parsers.semantic_ir import FileIR, ClassIR, FunctionIR, ImportIR, CallIR, ParameterIR
from app.models import Language as LangEnum


def _text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _get_docstring(node: Node, src: bytes) -> str | None:
    """Extract leading docstring from a function/class body."""
    body = node.child_by_field_name("body")
    if body and body.child_count > 0:
        first = body.children[0]
        if first.type == "expression_statement":
            expr = first.children[0] if first.children else None
            if expr and expr.type in ("string", "concatenated_string"):
                raw = _text(expr, src)
                return raw.strip("\"'").strip()
    return None


def _extract_params(params_node: Node, src: bytes) -> list[ParameterIR]:
    params = []
    if params_node is None:
        return params
    for child in params_node.named_children:
        if child.type in ("identifier",):
            params.append(ParameterIR(name=_text(child, src)))
        elif child.type in ("typed_parameter", "typed_default_parameter"):
            name_node = child.child_by_field_name("name") or child.named_children[0]
            type_node = child.child_by_field_name("type")
            params.append(ParameterIR(
                name=_text(name_node, src),
                type_hint=_text(type_node, src) if type_node else None,
            ))
        elif child.type == "default_parameter":
            name_node = child.child_by_field_name("name")
            if name_node:
                params.append(ParameterIR(name=_text(name_node, src)))
    return params


def _extract_function(node: Node, src: bytes, qualifier: str = "") -> FunctionIR:
    name_node = node.child_by_field_name("name")
    name = _text(name_node, src) if name_node else "<anon>"
    qualified = f"{qualifier}.{name}" if qualifier else name

    params_node = node.child_by_field_name("parameters")
    return_node = node.child_by_field_name("return_type")

    decorators = [
        _text(c, src) for c in node.parent.named_children
        if c.type == "decorator" and c.end_point[0] < node.start_point[0]
    ] if node.parent else []

    return FunctionIR(
        name=name,
        qualified_name=qualified,
        params=_extract_params(params_node, src),
        return_type=_text(return_node, src) if return_node else None,
        docstring=_get_docstring(node, src),
        decorators=decorators,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        is_async=node.type == "async_function_definition",
    )


def _collect_calls(node: Node, src: bytes, caller: str, calls: list[CallIR]):
    """Recursively collect function calls within a node."""
    if node.type == "call":
        func_node = node.child_by_field_name("function")
        if func_node:
            calls.append(CallIR(
                caller=caller,
                callee=_text(func_node, src),
                line=node.start_point[0] + 1,
            ))
    for child in node.named_children:
        _collect_calls(child, src, caller, calls)


def extract(root: Node, src: bytes, rel_path: str) -> FileIR:
    file_ir = FileIR(path=rel_path, language=LangEnum.PYTHON.value)

    for node in root.named_children:
        # ── Import ────────────────────────────────────────────────────────────
        if node.type == "import_statement":
            for name_node in node.named_children:
                file_ir.imports.append(ImportIR(module=_text(name_node, src)))

        elif node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            module = _text(module_node, src) if module_node else ""
            symbols = [
                _text(c, src) for c in node.named_children
                if c != module_node and c.type not in (".", "import")
            ]
            file_ir.imports.append(ImportIR(module=module, symbols=symbols))

        # ── Class ─────────────────────────────────────────────────────────────
        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            class_name = _text(name_node, src) if name_node else "<anon>"
            bases_node = node.child_by_field_name("superclasses")
            bases = [_text(b, src) for b in (bases_node.named_children if bases_node else [])]

            cls = ClassIR(
                name=class_name,
                qualified_name=class_name,
                bases=bases,
                docstring=_get_docstring(node, src),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            )

            body = node.child_by_field_name("body")
            if body:
                for child in body.named_children:
                    if child.type in ("function_definition", "async_function_definition"):
                        fn = _extract_function(child, src, qualifier=class_name)
                        cls.methods.append(fn)
                        _collect_calls(child, src, fn.qualified_name, file_ir.calls)
                    elif child.type in ("expression_statement",):
                        # Could be field assignment
                        if child.named_children and child.named_children[0].type == "assignment":
                            targets = child.named_children[0].child_by_field_name("left")
                            if targets:
                                cls.fields.append(_text(targets, src))

            file_ir.classes.append(cls)

        # ── Top-level function ────────────────────────────────────────────────
        elif node.type in ("function_definition", "async_function_definition"):
            fn = _extract_function(node, src)
            file_ir.functions.append(fn)
            _collect_calls(node, src, fn.qualified_name, file_ir.calls)

    return file_ir
