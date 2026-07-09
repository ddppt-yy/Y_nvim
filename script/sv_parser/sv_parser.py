#!/usr/bin/env python3
"""SystemVerilog Parser using verible-verilog-syntax

This module provides a SvParser class for parsing SystemVerilog files
and extracting module information including ports, parameters, and signals.
"""

import sys
import json
import subprocess
import collections
import dataclasses
from typing import Callable, Dict, Iterable, List, Optional, Union


# =============================================================================
# Tree Iterator Classes
# =============================================================================

CallableFilter = Callable[["Node"], bool]
KeyValueFilter = Dict[str, Union[str, List[str]]]
TreeIterator = "_TreeIteratorBase"


class _TreeIteratorBase:
    """Base class for tree iterators."""
    
    def __init__(self, tree: "Node",
                 filter_: Optional[CallableFilter] = None,
                 reverse_children: bool = False):
        self.tree = tree
        self.reverse_children = reverse_children
        self.filter_ = filter_ if filter_ else lambda n: True

    def __iter__(self) -> Iterable["Node"]:
        yield from self._iter_tree(self.tree)

    def _iter_children(self, tree: Optional["Node"]) -> Iterable["Node"]:
        if not tree or not hasattr(tree, "children"):
            return []
        return tree.children if not self.reverse_children \
                             else reversed(tree.children)

    def _iter_tree(self, tree: Optional["Node"]) -> Iterable["Node"]:
        raise NotImplementedError("Subclass must implement '_iter_tree' method")


class PreOrderTreeIterator(_TreeIteratorBase):
    """Pre-order tree iterator."""
    
    def _iter_tree(self, tree: Optional["Node"]) -> Iterable["Node"]:
        if self.filter_(tree):
            yield tree
        for child in self._iter_children(tree):
            yield from self._iter_tree(child)


class PostOrderTreeIterator(_TreeIteratorBase):
    """Post-order tree iterator."""
    
    def _iter_tree(self, tree: Optional["Node"]) -> Iterable["Node"]:
        for child in self._iter_children(tree):
            yield from self._iter_tree(child)
        if self.filter_(tree):
            yield tree


class LevelOrderTreeIterator(_TreeIteratorBase):
    """Level-order tree iterator."""
    
    def _iter_tree(self, tree: Optional["Node"]) -> Iterable["Node"]:
        queue = collections.deque([tree])
        while len(queue) > 0:
            n = queue.popleft()
            if self.filter_(n):
                yield n
            queue.extend(self._iter_children(n))


# =============================================================================
# Node Classes
# =============================================================================

class Node:
    """Base syntax tree node."""

    def __init__(self, parent: Optional["Node"] = None):
        self._parent: Optional["Node"] = None
        self._children: List["Node"] = []
        self.parent = parent

    @property
    def parent(self) -> Optional["Node"]:
        """Parent node."""
        return self._parent

    @parent.setter
    def parent(self, value: Optional["Node"]):
        """Set parent node, updating children lists accordingly."""
        if self._parent is value:
            return
        if self._parent is not None:
            self._parent._children = [c for c in self._parent._children if c is not self]
        self._parent = value
        if self._parent is not None:
            if self not in self._parent._children:
                self._parent._children.append(self)

    @property
    def children(self) -> List["Node"]:
        """Children nodes."""
        return self._children

    @children.setter
    def children(self, value: List["Node"]):
        """Set children nodes, updating parent references accordingly."""
        for child in self._children:
            if child._parent is self:
                child._parent = None
        self._children = list(value) if value else []
        for child in self._children:
            child._parent = self

    @property
    def syntax_data(self) -> Optional["SyntaxData"]:
        """Parent SyntaxData"""
        return self.parent.syntax_data if self.parent else None

    @property
    def start(self) -> Optional[int]:
        """Byte offset of node's first character in source text"""
        raise NotImplementedError("Subclass must implement 'start' property")

    @property
    def end(self) -> Optional[int]:
        """Byte offset of a character just past the node in source text."""
        raise NotImplementedError("Subclass must implement 'end' property")

    @property
    def text(self) -> str:
        """Source code fragment spanning all tokens in a node."""
        start = self.start
        end = self.end
        sd = self.syntax_data
        if ((start is not None) and (end is not None) and sd and sd.source_code
            and end <= len(sd.source_code)):
            return sd.source_code[start:end].decode("utf-8")
        return ""


class BranchNode(Node):
    """Syntax tree branch node"""

    def __init__(self, tag: str, parent: Optional[Node] = None,
                 children: Optional[List[Node]] = None):
        super().__init__(parent)
        self.tag = tag
        self.children = children if children is not None else []

    @property
    def start(self) -> Optional[int]:
        first_token = self.find(lambda n: isinstance(n, TokenNode),
                               iter_=PostOrderTreeIterator)
        return first_token.start if first_token else None

    @property
    def end(self) -> Optional[int]:
        last_token = self.find(lambda n: isinstance(n, TokenNode),
                              iter_=PostOrderTreeIterator, reverse_children=True)
        return last_token.end if last_token else None

    def iter_find_all(self, filter_: Union[CallableFilter, KeyValueFilter, None],
                      max_count: int = 0,
                      iter_: TreeIterator = LevelOrderTreeIterator,
                      **kwargs) -> Iterable[Node]:
        """Iterate all nodes matching specified filter."""
        def as_list(v):
            return v if isinstance(v, list) else [v]

        if filter_ and not callable(filter_):
            filters = filter_
            def f(node):
                for attr, value in filters.items():
                    if not hasattr(node, attr):
                        return False
                    if getattr(node, attr) not in as_list(value):
                        return False
                return True
            filter_ = f

        for node in iter_(self, filter_, **kwargs):
            yield node
            max_count -= 1
            if max_count == 0:
                break

    def find(self, filter_: Union[CallableFilter, KeyValueFilter, None],
             iter_: TreeIterator = LevelOrderTreeIterator, **kwargs) \
             -> Optional[Node]:
        """Find node matching specified filter."""
        return next(self.iter_find_all(filter_, max_count=1, iter_=iter_,
                    **kwargs), None)

    def find_all(self, filter_: Union[CallableFilter, KeyValueFilter, None],
                 max_count: int = 0, iter_: TreeIterator = LevelOrderTreeIterator,
                 **kwargs) -> List[Node]:
        """Find all nodes matching specified filter."""
        return list(self.iter_find_all(filter_, max_count=max_count, iter_=iter_,
                    **kwargs))


class RootNode(BranchNode):
    """Syntax tree root node."""
    
    def __init__(self, tag: str, syntax_data: Optional["SyntaxData"] = None,
                 children: Optional[List[Node]] = None):
        super().__init__(tag, None, children)
        self._syntax_data = syntax_data

    @property
    def syntax_data(self) -> Optional["SyntaxData"]:
        return self._syntax_data


class LeafNode(Node):
    """Syntax tree leaf node (used for null nodes)."""

    @property
    def start(self) -> None:
        return None

    @property
    def end(self) -> None:
        return None


class TokenNode(LeafNode):
    """Tree node with token data."""

    def __init__(self, tag: str, start: int, end: int,
                 parent: Optional[Node] = None):
        super().__init__(parent)
        self.tag = tag
        self._start = start
        self._end = end

    @property
    def start(self) -> int:
        return self._start

    @property
    def end(self) -> int:
        return self._end


# =============================================================================
# Data Classes
# =============================================================================

@dataclasses.dataclass
class SyntaxData:
    """Container for parsed syntax data."""
    source_code: Optional[bytes] = None
    tree: Optional[RootNode] = None


# =============================================================================
# Parser Functions
# =============================================================================

def _transform_tree(tree, data: SyntaxData, skip_null: bool) -> RootNode:
    """Transform JSON tree to Node tree."""
    
    def transform(tree):
        if tree is None:
            return None
        if "children" in tree:
            children = [
                transform(child) or LeafNode()
                for child in tree["children"]
                if not (skip_null and child is None)
            ]
            tag = tree["tag"]
            return BranchNode(tag, children=children)
        tag = tree["tag"]
        start = tree["start"]
        end = tree["end"]
        return TokenNode(tag, start, end)

    if "children" not in tree:
        return None

    children = [
        transform(child) or LeafNode()
        for child in tree["children"]
        if not (skip_null and child is None)
    ]
    tag = tree["tag"]
    return RootNode(tag, syntax_data=data, children=children)


def parse_verilog_file(file_path: str, executable: str = "verible-verilog-syntax") -> Optional[SyntaxData]:
    """Parse a SystemVerilog file using verible-verilog-syntax.
    
    Args:
        file_path: Path to the SystemVerilog file.
        executable: Path to verible-verilog-syntax binary.
        
    Returns:
        SyntaxData object containing the parsed tree, or None on error.
    """
    # Run verible-verilog-syntax with JSON export
    args = [executable, "-export_json", "-printtree", file_path]
    
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        
        if proc.returncode != 0 and not proc.stdout:
            return None
        
        json_data = json.loads(proc.stdout)
        
        # Get the file data (key is the file path)
        for fp, file_json in json_data.items():
            file_data = SyntaxData()
            
            # Read source code
            with open(fp, "rb") as f:
                file_data.source_code = f.read()
            
            # Transform tree
            if "tree" in file_json:
                file_data.tree = _transform_tree(
                    file_json["tree"], file_data, skip_null=False)
            
            return file_data
        
        return None
        
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        return None


# =============================================================================
# SvParser Class
# =============================================================================

class SvParser:
    """SystemVerilog file parser using verible-verilog-syntax.
    
    This class parses SystemVerilog files and extracts module information
    including ports, parameters, localparameters, and signals.
    
    Attributes:
        file_path (str): Path to the SystemVerilog file.
        syntax_data: Parsed syntax data from verible-verilog-syntax.
        module_info (dict): Extracted module information.
    """

    _DATA_TYPE_KEYWORDS = (
        "wire", "tri", "supply0", "supply1", "wand", "wor", "triand",
        "trior", "tri0", "tri1", "uwire", "reg", "logic", "bit", "byte",
        "shortint", "int", "longint", "integer", "time", "real",
        "realtime", "shortreal"
    )
    _IDENTIFIER_TAGS = ("SymbolIdentifier", "EscapedIdentifier")
    _PORT_DIRECTIONS = ("input", "output", "inout")
    _MODPORT_DIRECTIONS = ("input", "output", "inout", "ref")
    
    def __init__(self, file_path: str, executable: str = "verible-verilog-syntax"):
        """Initialize the parser with a file path.
        
        Args:
            file_path: Path to the SystemVerilog file to parse.
            executable: Path to verible-verilog-syntax binary.
        """
        self.file_path = file_path
        self.executable = executable
        self.syntax_data = None
        self.module_info = None
        self._parse_file()
    
    def _parse_file(self):
        """Parse the SystemVerilog file using verible-verilog-syntax."""
        self.syntax_data = parse_verilog_file(self.file_path, self.executable)

    @staticmethod
    def _tag(node) -> str:
        """Return a node tag or an empty string for null/leaf placeholders."""
        return getattr(node, 'tag', "") if node is not None else ""

    def _is_tag(self, node, tags: Union[str, Iterable[str]]) -> bool:
        """Check a node tag against one tag or a collection of tags."""
        if isinstance(tags, str):
            return self._tag(node) == tags
        return self._tag(node) in tags

    def _iter_children(self, node) -> Iterable[Node]:
        """Iterate real children from a node-like object."""
        return (child for child in getattr(node, 'children', []) if child is not None)

    def _find_direct_child(self, node, tags: Union[str, Iterable[str]]):
        """Find a direct child by tag without descending into nested syntax."""
        for child in self._iter_children(node):
            if self._is_tag(child, tags):
                return child
        return None
    
    def _get_text(self, node) -> str:
        """Get text from a node, handling None cases.
        
        Args:
            node: A syntax tree node.
            
        Returns:
            The text content of the node, or empty string if None.
        """
        if node is None:
            return ""
        return node.text.strip()

    def _get_compact_text(self, node) -> str:
        """Concatenate descendant token text without preserving whitespace."""
        if node is None:
            return ""
        if not getattr(node, 'children', None):
            return self._get_text(node)
        return "".join(self._get_compact_text(child)
                       for child in self._iter_children(node))
    
    def _get_expression_text(self, node) -> str:
        """Extract expression text from an expression node.
        
        This handles various expression types including binary expressions,
        function calls, references, and numbers.
        
        Args:
            node: An expression node (kExpression, kBinaryExpression, etc.)
            
        Returns:
            The expression as a string.
        """
        if node is None:
            return ""
        
        # If it's a token node, return its text
        if not hasattr(node, 'children') or not node.children:
            return self._get_text(node)
        
        tag = node.tag if hasattr(node, 'tag') else ""
        
        # Handle binary expressions
        if tag == "kBinaryExpression":
            parts = []
            for child in node.children:
                if child is None:
                    continue
                child_text = self._get_expression_text(child)
                if child_text:
                    parts.append(child_text)
            return "".join(parts)
        
        # Handle function call / reference
        if tag == "kFunctionCall" or tag == "kReference":
            return self._get_expression_text_from_reference(node)
        
        # Handle kExpression wrapper
        if tag == "kExpression":
            if len(node.children) == 1:
                return self._get_expression_text(node.children[0])
            return "".join(self._get_expression_text(child)
                           for child in node.children if child is not None)
        
        # Handle number
        if tag == "kNumber":
            return self._get_text(node)
        
        # Default: rebuild the expression from child tokens so constructs like
        # concatenation/replication do not collapse to the first token.
        return "".join(self._get_expression_text(child)
                       for child in node.children if child is not None)
    
    def _get_expression_text_from_reference(self, node) -> str:
        """Extract text from a reference node (like AA, BB, etc.).
        
        Args:
            node: A kReference or kFunctionCall node.
            
        Returns:
            The reference as a string.
        """
        if node is None:
            return ""
        
        result = ""
        for child in node.children:
            if child is None:
                continue
            tag = child.tag if hasattr(child, 'tag') else ""
            if tag == "kLocalRoot":
                result += self._get_expression_text_from_local_root(child)
            elif tag in ("kUnqualifiedId", "SymbolIdentifier", "EscapedIdentifier"):
                result += self._get_text(child)
            elif tag == ".":
                result += "."
            else:
                result += self._get_expression_text(child)
        return result
    
    def _get_expression_text_from_local_root(self, node) -> str:
        """Extract text from kLocalRoot node.
        
        Args:
            node: A kLocalRoot node.
            
        Returns:
            The identifier text.
        """
        if node is None:
            return ""

        text = self._get_text(node)
        if text:
            return text
        
        for child in node.children:
            if child is None:
                continue
            tag = child.tag if hasattr(child, 'tag') else ""
            if tag == "kUnqualifiedId":
                for subchild in child.children:
                    if subchild and hasattr(subchild, 'tag') and subchild.tag in ("SymbolIdentifier", "EscapedIdentifier"):
                        return self._get_text(subchild)
        return ""
    
    def _get_packed_dimensions(self, node) -> str:
        """Extract packed dimensions from a node.
        
        Args:
            node: A kPackedDimensions node.
            
        Returns:
            The packed dimensions as a string (e.g., "[AA-1:0]").
        """
        return self._get_dimensions(node)
    
    def _get_dimension_text(self, node) -> str:
        """Extract dimension text from kDeclarationDimensions node.
        
        Args:
            node: A kDeclarationDimensions node.
            
        Returns:
            The dimensions as a string.
        """
        return self._get_dimensions(node)

    def _get_dimensions(self, node) -> str:
        """Extract compact text from a dimension wrapper node."""
        if node is None:
            return ""

        result = ""
        for child in self._iter_children(node):
            tag = self._tag(child)
            if tag == "kDimensionRange":
                result += self._get_single_dimension_range(child)
            elif tag == "kDimensionScalar":
                result += self._get_dimension_scalar(child)
            elif tag == "kDeclarationDimensions":
                result += self._get_dimensions(child)
        return result
    
    def _get_single_dimension_range(self, node) -> str:
        """Extract a single dimension range [expr:expr].
        
        Args:
            node: A kDimensionRange node.
            
        Returns:
            The dimension range as a string.
        """
        if node is None:
            return ""
        
        parts = []
        for child in self._iter_children(node):
            tag = self._tag(child)
            if tag == "[":
                parts.append("[")
            elif tag == "]":
                parts.append("]")
            elif tag == ":":
                parts.append(":")
            elif tag == "kExpression":
                parts.append(self._get_expression_text(child))
            elif tag == "kBinaryExpression":
                parts.append(self._get_expression_text(child))
        
        return "".join(parts)
    
    def _get_dimension_scalar(self, node) -> str:
        """Extract a scalar dimension [expr].
        
        Args:
            node: A kDimensionScalar node.
            
        Returns:
            The scalar dimension as a string.
        """
        if node is None:
            return ""
        
        parts = []
        for child in self._iter_children(node):
            tag = self._tag(child)
            if tag == "[":
                parts.append("[")
            elif tag == "]":
                parts.append("]")
            elif tag == "kExpressionList":
                for expr in child.children:
                    if expr and hasattr(expr, 'tag') and expr.tag == "kExpression":
                        parts.append(self._get_expression_text(expr))
            elif tag == "kExpression":
                parts.append(self._get_expression_text(child))
        
        return "".join(parts)
    
    def _get_unpacked_dimensions(self, node) -> str:
        """Extract unpacked dimensions from a node.
        
        Args:
            node: A kUnpackedDimensions node.
            
        Returns:
            The unpacked dimensions as a string.
        """
        return self._get_dimensions(node)
    
    def _get_data_type_from_node(self, data_type) -> str:
        """Extract a data type string from a kDataType node.
        
        Args:
            data_type: A kDataType node.
            
        Returns:
            The data type as a string (e.g., "logic", "op", or interface name).
        """
        if data_type is None:
            return ""

        # Some old-style declarations expose net/variable type keywords as
        # direct kDataType children instead of wrapping them in kDataTypePrimitive.
        for child in self._iter_children(data_type):
            tag = self._tag(child)
            if tag in self._DATA_TYPE_KEYWORDS:
                return tag
        
        # Check for primitive type (logic, bit, etc.)
        primitive = data_type.find({"tag": "kDataTypePrimitive"})
        if primitive:
            type_token = primitive.find({"tag": list(self._IDENTIFIER_TAGS)})
            if type_token:
                return self._get_text(type_token)
            # Try to find logic, bit, etc. directly
            for child in self._iter_children(primitive):
                tag = self._tag(child)
                if tag in self._DATA_TYPE_KEYWORDS:
                    return tag
        
        # Check for interface port header (intf.master, intf.slave)
        interface_header = data_type.find({"tag": "kInterfacePortHeader"})
        if interface_header:
            return self._get_interface_port_type(interface_header)
        
        # Check direct local root children only. Nested local roots can come
        # from packed-dimension expressions such as [WIDTH-1:0].
        for child in self._iter_children(data_type):
            if self._tag(child) != "kLocalRoot":
                continue
            unqualified_id = child.find({"tag": "kUnqualifiedId"})
            if unqualified_id:
                type_id = unqualified_id.find({"tag": list(self._IDENTIFIER_TAGS)})
                if type_id:
                    return self._get_text(type_id)

        return ""

    def _get_interface_port_type(self, interface_header) -> list:
        """Extract interface port type (e.g., ['intf', 'master']).
        
        Args:
            interface_header: A kInterfacePortHeader node.
            
        Returns:
            A list containing interface name and modport.
        """
        result = []
        unqualified_id = interface_header.find({"tag": "kUnqualifiedId"})
        if unqualified_id:
            for child in self._iter_children(unqualified_id):
                if self._tag(child) in self._IDENTIFIER_TAGS:
                    result.append(self._get_text(child))
        
        # Get modport if present
        for child in self._iter_children(interface_header):
            if self._tag(child) in self._IDENTIFIER_TAGS:
                result.append(self._get_text(child))
        
        return result
    
    def _get_port_direction(self, port_decl) -> str:
        """Extract port direction from a port declaration.
        
        Args:
            port_decl: A kPortDeclaration node.
            
        Returns:
            The direction as a string (input, output, inout, or "" for interface).
        """
        for child in self._iter_children(port_decl):
            if self._tag(child) in self._PORT_DIRECTIONS:
                return self._tag(child)
        return ""
    
    def _get_port_name(self, port_decl) -> str:
        """Extract port name from a port declaration.
        
        Args:
            port_decl: A kPortDeclaration node.
            
        Returns:
            The port name as a string.
        """
        return self._get_identifier_name(port_decl)
    
    def _parse_port_declaration(self, port_decl) -> tuple:
        """Parse a single port declaration.
        
        Args:
            port_decl: A kPortDeclaration node.
            
        Returns:
            A tuple representing the port information.
        """
        direction = self._get_port_direction(port_decl)
        data_type_node = port_decl.find({"tag": "kDataType"})
        
        # Check if it's an interface port
        if data_type_node:
            interface_header = data_type_node.find({"tag": "kInterfacePortHeader"})
            if interface_header:
                name = self._get_port_name(port_decl)
                intf_type = self._get_interface_port_type(interface_header)
                return (name, intf_type)
        
        # Regular port
        name = self._get_port_name(port_decl)
        data_type = self._get_data_type_from_node(data_type_node)
        
        # Get packed dimensions
        packed_dims = ""
        packed_node = port_decl.find({"tag": "kPackedDimensions"})
        if packed_node:
            packed_dims = self._get_packed_dimensions(packed_node)
        
        # Get unpacked dimensions
        unpacked_dims = ""
        unpacked_node = port_decl.find({"tag": "kUnpackedDimensions"})
        if unpacked_node:
            unpacked_dims = self._get_unpacked_dimensions(unpacked_node)
        
        return (name, direction, data_type, packed_dims, unpacked_dims)

    def _get_module_header_port_names(self, header) -> List[str]:
        """Extract non-ANSI port names from a module header."""
        names = []
        if header is None:
            return names

        port_list = header.find({"tag": "kPortDeclarationList"})
        if port_list is None:
            return names

        for port in port_list.children:
            if not port or not hasattr(port, 'tag') or port.tag != "kPort":
                continue
            name = self._get_identifier_name(port)
            if name:
                names.append(name)
        return names

    def _get_identifier_name(self, node) -> str:
        """Extract an identifier name from common identifier wrapper nodes."""
        if node is None:
            return ""

        tag = self._tag(node)
        if tag in self._IDENTIFIER_TAGS:
            return self._get_text(node)

        unqualified_id = node.find({"tag": "kUnqualifiedId"}) \
            if hasattr(node, 'find') else None
        if unqualified_id:
            name_id = unqualified_id.find({"tag": list(self._IDENTIFIER_TAGS)})
            if name_id:
                return self._get_text(name_id)

        name_id = node.find({"tag": list(self._IDENTIFIER_TAGS)}) \
            if hasattr(node, 'find') else None
        return self._get_text(name_id) if name_id else ""

    def _get_direct_identifier_name(self, node) -> str:
        """Extract a declared name from direct identifier children only."""
        if node is None:
            return ""

        for child in self._iter_children(node):
            tag = self._tag(child)
            if tag in self._IDENTIFIER_TAGS:
                return self._get_text(child)
            if tag == "kUnqualifiedId":
                return self._get_identifier_name(child)
        return ""

    def _get_module_port_declared_type(self, module_port_decl,
                                       direction: str) -> str:
        """Recover old-style port type keywords omitted from kDataType."""
        if not direction:
            return ""

        parts = module_port_decl.text.strip().split()
        if len(parts) > 1 and parts[0] == direction and \
                parts[1] in self._DATA_TYPE_KEYWORDS:
            return parts[1]
        return ""

    def _parse_module_port_declaration(self, module_port_decl) -> List[tuple]:
        """Parse old-style Verilog module port declarations.

        Args:
            module_port_decl: A kModulePortDeclaration node.

        Returns:
            A list of port tuples, one per declared identifier.
        """
        direction = ""
        for child in self._iter_children(module_port_decl):
            if self._tag(child) in self._PORT_DIRECTIONS:
                direction = self._tag(child)
                break

        data_type_node = module_port_decl.find({"tag": "kDataType"})
        data_type = self._get_data_type_from_node(data_type_node)
        if not data_type:
            data_type = self._get_module_port_declared_type(
                module_port_decl, direction)

        packed_dims = ""
        if data_type_node:
            packed_node = data_type_node.find({"tag": "kPackedDimensions"})
            if packed_node:
                packed_dims = self._get_packed_dimensions(packed_node)

        ports = []
        list_tags = (
            "kIdentifierList",
            "kIdentifierUnpackedDimensionsList",
            "kPortIdentifierList",
        )
        for list_tag in list_tags:
            id_list = module_port_decl.find({"tag": list_tag})
            if id_list is None:
                continue

            for item in self._iter_children(id_list):
                if self._tag(item) in (",", ";"):
                    continue

                name = self._get_identifier_name(item)
                if not name:
                    continue

                unpacked_dims = ""
                unpacked_node = item.find({"tag": "kUnpackedDimensions"}) \
                    if hasattr(item, 'find') else None
                if unpacked_node:
                    unpacked_dims = self._get_unpacked_dimensions(unpacked_node)

                ports.append((name, direction, data_type,
                              packed_dims, unpacked_dims))

        return ports

    def _order_ports_by_header(self, ports: List[tuple],
                               header_order: List[str]) -> List[tuple]:
        """Order old-style port declarations by the module header list."""
        if not header_order:
            return ports

        ports_by_name = {port[0]: port for port in ports}
        ordered = [ports_by_name[name] for name in header_order
                   if name in ports_by_name]
        ordered_names = set(header_order)
        ordered.extend(port for port in ports if port[0] not in ordered_names)
        return ordered

    def _get_type_info_data_type(self, type_info, default: str = "") -> str:
        """Extract primitive or user-defined type text from kTypeInfo."""
        if type_info is None:
            return default

        for child in self._iter_children(type_info):
            tag = self._tag(child)
            if tag in self._DATA_TYPE_KEYWORDS:
                return tag

        unqualified_id = type_info.find({"tag": "kUnqualifiedId"})
        if unqualified_id:
            type_id = unqualified_id.find({"tag": list(self._IDENTIFIER_TAGS)})
            if type_id:
                return self._get_text(type_id)

        return default

    def _get_trailing_assign_value(self, decl) -> str:
        """Extract the expression value from a trailing assignment."""
        trailing_assign = decl.find({"tag": "kTrailingAssign"})
        if trailing_assign is None:
            return ""

        expr = trailing_assign.find({"tag": "kExpression"})
        return self._get_expression_text(expr) if expr else ""

    def _parse_param_declaration(self, param_decl, default_data_type: str) -> tuple:
        """Parse parameter/localparam declarations with a shared shape."""
        param_type = param_decl.find({"tag": "kParamType"})

        data_type = default_data_type
        packed_dim = ""
        name = ""

        if param_type:
            data_type = self._get_type_info_data_type(
                param_type.find({"tag": "kTypeInfo"}),
                default_data_type,
            )

            packed_node = param_type.find({"tag": "kPackedDimensions"})
            if packed_node:
                packed_dim = self._get_packed_dimensions(packed_node)

            name = self._get_direct_identifier_name(param_type)

        return (name, self._get_trailing_assign_value(param_decl),
                data_type, packed_dim)

    @staticmethod
    def _none_if_empty(value: str) -> str:
        """Normalize empty signal dimensions to the historical string value."""
        return value if value else "None"
    
    def _parse_parameter(self, param_decl) -> tuple:
        """Parse a single parameter declaration.
        
        Args:
            param_decl: A kParamDeclaration node.
            
        Returns:
            A tuple representing the parameter information (name, value, type, packed_dim).
        """
        return self._parse_param_declaration(param_decl, "None")
    
    def _parse_localparam(self, param_decl) -> tuple:
        """Parse a single localparam declaration.
        
        Args:
            param_decl: A kParamDeclaration node with localparam keyword.
            
        Returns:
            A tuple representing the localparam information (name, value, type, packed_dim).
        """
        return self._parse_param_declaration(param_decl, "")
    
    def _parse_data_declaration(self, data_decl) -> tuple:
        """Parse a data declaration (logic, wire, user-defined types, interfaces).
        
        Args:
            data_decl: A kDataDeclaration node.
            
        Returns:
            A tuple representing the signal information (name, type, packed_dim, unpacked_dim).
        """
        data_type = ""
        packed_dim = ""
        unpacked_dim = ""
        name = ""
        
        # Get instantiation base (contains type info)
        inst_base = data_decl.find({"tag": "kInstantiationBase"})
        if inst_base:
            inst_type = inst_base.find({"tag": "kInstantiationType"})
            if inst_type:
                dt_node = inst_type.find({"tag": "kDataType"})
                if dt_node:
                    data_type = self._get_data_type_from_node(dt_node)
                    packed_node = self._find_direct_child(dt_node,
                                                          "kPackedDimensions")
                    if packed_node:
                        packed_dim = self._get_packed_dimensions(packed_node)
            
            # Get signal name from kGateInstanceRegisterVariableList
            reg_var_list = inst_base.find({"tag": "kGateInstanceRegisterVariableList"})
            if reg_var_list:
                # Check for kRegisterVariable (for logic signals)
                reg_var = reg_var_list.find({"tag": "kRegisterVariable"})
                if reg_var:
                    name = self._get_direct_identifier_name(reg_var)
                    # Get unpacked dimensions
                    unpacked_node = reg_var.find({"tag": "kUnpackedDimensions"})
                    if unpacked_node:
                        unpacked_dim = self._get_unpacked_dimensions(unpacked_node)
                else:
                    # Check for kGateInstance (for interface instances)
                    gate_inst = reg_var_list.find({"tag": "kGateInstance"})
                    if gate_inst:
                        # Check if it's a module instantiation (has kPortActualList)
                        port_actual = gate_inst.find({"tag": "kPortActualList"})
                        if port_actual:
                            # This is a module instantiation, skip it
                            return ("", "", "", "")
                        
                        name = self._get_direct_identifier_name(gate_inst)
                        # Check for parentheses (interface instance)
                        has_paren = False
                        for gchild in self._iter_children(gate_inst):
                            tag = self._tag(gchild)
                            if tag == "(":
                                has_paren = True
                                name += "("
                            elif tag == ")":
                                name += ")"
                        # If no parentheses but it's an interface, add ()
                        if not has_paren and data_type and data_type.endswith("_if"):
                            name += "()"
        
        return (name, data_type, self._none_if_empty(packed_dim),
                self._none_if_empty(unpacked_dim))
    
    def _parse_net_declaration(self, net_decl) -> tuple:
        """Parse a net declaration (wire declarations).
        
        Args:
            net_decl: A kNetDeclaration node.
            
        Returns:
            A tuple representing the signal information (name, type, packed_dim, unpacked_dim).
        """
        data_type = ""
        packed_dim = ""
        unpacked_dim = ""
        name = ""
        
        dt_node = net_decl.find({"tag": "kDataType"})
        data_type = self._get_data_type_from_node(dt_node)
        
        # Get packed dimensions from kDataTypeImplicitIdDimensions
        implicit_dims = net_decl.find({"tag": "kDataTypeImplicitIdDimensions"})
        if implicit_dims:
            packed_node = implicit_dims.find({"tag": "kPackedDimensions"})
            if packed_node:
                packed_dim = self._get_packed_dimensions(packed_node)
        
        # Get name and unpacked dimensions from kNetVariableDeclarationAssign
        net_var_assign = net_decl.find({"tag": "kNetVariableDeclarationAssign"})
        if net_var_assign:
            net_var = net_var_assign.find({"tag": "kNetVariable"})
            if net_var:
                name = self._get_direct_identifier_name(net_var)
                unpacked_node = net_var.find({"tag": "kUnpackedDimensions"})
                if unpacked_node:
                    unpacked_dim = self._get_unpacked_dimensions(unpacked_node)

        return (name, data_type, self._none_if_empty(packed_dim),
                self._none_if_empty(unpacked_dim))
    
    def _parse_import(self, import_decl) -> str:
        """Parse a single import declaration.
        
        Args:
            import_decl: A kPackageImportItem node.
            
        Returns:
            A string representing the import (e.g., "pkg_mthc_::*").
        """
        return self._get_compact_text(import_decl)

    def _new_module_info(self) -> dict:
        """Create the public module-info shape expected by callers."""
        return {
            'name': '',
            # Kept for backwards compatibility. Package imports are reported
            # through 'import'; this parser does not collect package definitions.
            'package': [],
            'para': [],
            'lpara': [],
            'port': [],
            'signal': [],
            'import': []
        }

    def _new_interface_info(self) -> dict:
        """Create module-info compatible output for an interface declaration."""
        result = self._new_module_info()
        result['interface'] = {
            'port': [],
            'modport': {}
        }
        return result

    def _is_header_parameter(self, param_decl) -> bool:
        """Return True for parameter declarations from an ANSI header."""
        return self._tag(getattr(param_decl, 'parent', None)) == "kFormalParameterList"

    def _is_localparam(self, param_decl) -> bool:
        """Return True when a kParamDeclaration starts with localparam."""
        return any(self._tag(child) == "localparam"
                   for child in self._iter_children(param_decl))

    def _is_module_header_child(self, node) -> bool:
        """Return True for declarations already handled from kModuleHeader."""
        return self._tag(getattr(node, 'parent', None)) == "kModuleHeader"

    def _is_module_item_child(self, node) -> bool:
        """Return True for declarations directly under a module/interface body."""
        return self._tag(getattr(node, 'parent', None)) == "kModuleItemList"

    @staticmethod
    def _interface_dim(value: str) -> str:
        """Use module-port style empty dimensions for interface signal ports."""
        return "" if value == "None" else value

    def _to_interface_port(self, signal_info: tuple) -> tuple:
        """Convert a signal tuple to an interface port tuple without direction."""
        name, data_type, packed_dim, unpacked_dim = signal_info
        return (
            name,
            data_type,
            self._interface_dim(packed_dim),
            self._interface_dim(unpacked_dim),
        )

    def _parse_modport_ports_declaration(self, ports_decl) -> List[tuple]:
        """Parse one modport direction group into (signal, direction) tuples."""
        direction = ""
        for child in self._iter_children(ports_decl):
            if self._tag(child) in self._MODPORT_DIRECTIONS:
                direction = self._tag(child)
                break

        if not direction:
            return []

        ports = []
        for port in self._iter_children(ports_decl):
            if self._tag(port) != "kModportSimplePort":
                continue
            name = self._get_identifier_name(port)
            if name:
                ports.append((name, direction))
        return ports

    def _parse_modport_item(self, modport_item) -> tuple:
        """Parse a single modport item into (name, port_list)."""
        name = self._get_direct_identifier_name(modport_item)
        ports = []
        port_list = modport_item.find({"tag": "kModportPortList"})
        if port_list:
            for child in self._iter_children(port_list):
                if self._tag(child) != "kModportSimplePortsDeclaration":
                    continue
                ports.extend(self._parse_modport_ports_declaration(child))
        return name, ports

    def _parse_modport_declaration(self, modport_decl) -> dict:
        """Parse modport declarations grouped by modport name."""
        modports = {}
        item_list = modport_decl.find({"tag": "kModportItemList"})
        if item_list is None:
            return modports

        for item in self._iter_children(item_list):
            if self._tag(item) != "kModportItem":
                continue
            name, ports = self._parse_modport_item(item)
            if name:
                modports.setdefault(name, []).extend(ports)
        return modports

    def _append_header_info(self, result: dict, declaration) -> Optional[Node]:
        """Fill declaration name and ANSI parameters from its header."""
        header = declaration.find({"tag": "kModuleHeader"})
        if header is None:
            return None

        name_id = header.find({"tag": list(self._IDENTIFIER_TAGS)})
        if name_id:
            result['name'] = self._get_text(name_id)

        for param in header.iter_find_all({"tag": "kParamDeclaration"}):
            result['para'].append(self._parse_parameter(param))

        return header

    def _append_imports(self, result: dict, declaration):
        """Append package imports from a module/interface declaration."""
        for import_decl in declaration.iter_find_all({"tag": "kPackageImportItem"}):
            import_str = self._parse_import(import_decl)
            if import_str:
                result['import'].append(import_str)

    def _append_body_params(self, result: dict, declaration):
        """Append non-header parameters and localparameters."""
        for param_decl in declaration.iter_find_all({"tag": "kParamDeclaration"}):
            if self._is_header_parameter(param_decl):
                continue

            if self._is_localparam(param_decl):
                result['lpara'].append(self._parse_localparam(param_decl))
            else:
                result['para'].append(self._parse_parameter(param_decl))

    def _collect_signal_entries(self, declaration,
                                top_level_only: bool = False) -> List[tuple]:
        """Collect data/net declarations ordered by source position."""
        signal_entries = []

        for data_decl in declaration.iter_find_all({"tag": "kDataDeclaration"}):
            if self._is_module_header_child(data_decl):
                continue
            if top_level_only and not self._is_module_item_child(data_decl):
                continue

            signal_info = self._parse_data_declaration(data_decl)
            if signal_info[0]:
                pos = data_decl.start if data_decl.start is not None else 0
                signal_entries.append((pos, signal_info))

        for net_decl in declaration.iter_find_all({"tag": "kNetDeclaration"}):
            if top_level_only and not self._is_module_item_child(net_decl):
                continue

            signal_info = self._parse_net_declaration(net_decl)
            if signal_info[0]:
                pos = net_decl.start if net_decl.start is not None else 0
                signal_entries.append((pos, signal_info))

        signal_entries.sort(key=lambda x: x[0])
        return signal_entries

    def _parse_module_declaration(self, module) -> dict:
        """Build parser output for a module declaration."""
        result = self._new_module_info()
        header = self._append_header_info(result, module)
        header_port_order = []

        if header:
            header_port_order = self._get_module_header_port_names(header)
            for port in header.iter_find_all({"tag": "kPortDeclaration"}):
                result['port'].append(self._parse_port_declaration(port))

        if not result['port']:
            module_ports = []
            for module_port_decl in module.iter_find_all(
                    {"tag": "kModulePortDeclaration"}):
                module_ports.extend(
                    self._parse_module_port_declaration(module_port_decl))
            result['port'] = self._order_ports_by_header(
                module_ports, header_port_order)

        self._append_imports(result, module)
        self._append_body_params(result, module)

        signal_entries = self._collect_signal_entries(module)
        result['signal'] = [info for _, info in signal_entries]

        return result

    def _parse_interface_declaration(self, interface_decl) -> dict:
        """Build parser output for a SystemVerilog interface declaration."""
        result = self._new_interface_info()
        self._append_header_info(result, interface_decl)
        self._append_imports(result, interface_decl)
        self._append_body_params(result, interface_decl)

        signal_entries = self._collect_signal_entries(
            interface_decl, top_level_only=True)
        result['interface']['port'] = [
            self._to_interface_port(info) for _, info in signal_entries
        ]

        for modport_decl in interface_decl.iter_find_all(
                {"tag": "kModportDeclaration"}):
            for name, ports in self._parse_modport_declaration(
                    modport_decl).items():
                result['interface']['modport'].setdefault(name, []).extend(ports)

        return result

    def get_sv_port(self) -> dict:
        """Get module information including ports, parameters, and signals.

        Returns:
            A dictionary containing:
                - name: Module name
                - para: List of parameter tuples
                - lpara: List of localparam tuples
                - port: List of port tuples
                - signal: List of signal tuples
        """
        if self.syntax_data is None or self.syntax_data.tree is None:
            return {}

        module = self.syntax_data.tree.find({"tag": "kModuleDeclaration"})
        if module:
            result = self._parse_module_declaration(module)
            self.module_info = result
            return result

        interface_decl = self.syntax_data.tree.find({"tag": "kInterfaceDeclaration"})
        if interface_decl:
            result = self._parse_interface_declaration(interface_decl)
            self.module_info = result
            return result

        return {}


def main():
    """Test the parser with test.sv."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <sv_file>")
        return 1
    
    sv_file = sys.argv[1]
    parser = SvParser(sv_file)
    result = parser.get_sv_port()
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
