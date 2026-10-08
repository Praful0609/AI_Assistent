"""Java Tree-sitter AST extractor."""
from tree_sitter import Node
from parsers.semantic_ir import FileIR, ClassIR, FunctionIR, ImportIR, CallIR, ParameterIR
from app.models import Language as LangEnum


def _text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _collect_calls(node: Node, src: bytes, caller: str, calls: list[CallIR]):
    if node.type == "method_invocation":
        name_node = node.child_by_field_name("name")
        if name_node:
            calls.append(CallIR(caller=caller, callee=_text(name_node, src), line=node.start_point[0] + 1))
    for child in node.named_children:
        _collect_calls(child, src, caller, calls)


def _extract_method(node: Node, src: bytes, class_name: str) -> FunctionIR:
    name_node = node.child_by_field_name("name")
    name = _text(name_node, src) if name_node else "<anon>"

    params = []
    params_node = node.child_by_field_name("parameters")
    if params_node:
        for param in params_node.named_children:
            if param.type == "formal_parameter":
                p_name = param.child_by_field_name("name")
                p_type = param.child_by_field_name("type")
                params.append(ParameterIR(
                    name=_text(p_name, src) if p_name else "",
                    type_hint=_text(p_type, src) if p_type else None,
                ))

    return_node = node.child_by_field_name("type")
    modifiers = [_text(c, src) for c in node.named_children if c.type == "modifiers"]

    return FunctionIR(
        name=name,
        qualified_name=f"{class_name}.{name}",
        params=params,
        return_type=_text(return_node, src) if return_node else None,
        is_static="static" in " ".join(modifiers),
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
    )


def extract(root: Node, src: bytes, rel_path: str) -> FileIR:
    file_ir = FileIR(path=rel_path, language=LangEnum.JAVA.value)

    for node in root.named_children:
        if node.type == "import_declaration":
            path_node = node.named_children[0] if node.named_children else None
            if path_node:
                module_parts = _text(path_node, src).split(".")
                module = ".".join(module_parts[:-1])
                symbol = module_parts[-1]
                file_ir.imports.append(ImportIR(module=module, symbols=[symbol]))

        elif node.type in ("class_declaration", "interface_declaration", "enum_declaration"):
            name_node = node.child_by_field_name("name")
            class_name = _text(name_node, src) if name_node else "<anon>"

            superclass = node.child_by_field_name("superclass")
            interfaces = node.child_by_field_name("super_interfaces")
            bases = []
            if superclass:
                bases.append(_text(superclass, src).lstrip("extends ").strip())
            if interfaces:
                for iface in interfaces.named_children:
                    if iface.type == "type_list":
                        bases += [_text(c, src) for c in iface.named_children]

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
                    if child.type in ("method_declaration", "constructor_declaration"):
                        fn = _extract_method(child, src, class_name)
                        cls.methods.append(fn)
                        _collect_calls(child, src, fn.qualified_name, file_ir.calls)

            file_ir.classes.append(cls)

    return file_ir
