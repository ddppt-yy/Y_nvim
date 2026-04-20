#!/usr/bin/env python3
"""SystemVerilog Parser using verible-verilog-syntax

This module provides a SvParser class for parsing SystemVerilog files
and extracting module information including ports, parameters, and signals.
"""

import sys
import os
import json
import subprocess
import collections
import dataclasses
from typing import Any, Callable, Dict, Iterable, List, Optional, Union


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
            if node.children:
                return self._get_expression_text(node.children[0])
            return ""
        
        # Handle number
        if tag == "kNumber":
            return self._get_text(node)
        
        # Default: return text
        return self._get_text(node)
    
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
        if node is None:
            return ""
        
        result = ""
        for child in node.children:
            if child is None:
                continue
            tag = child.tag if hasattr(child, 'tag') else ""
            if tag == "kDeclarationDimensions":
                result += self._get_dimension_text(child)
            elif tag == "kDimensionRange":
                result += self._get_single_dimension_range(child)
        
        return result
    
    def _get_dimension_text(self, node) -> str:
        """Extract dimension text from kDeclarationDimensions node.
        
        Args:
            node: A kDeclarationDimensions node.
            
        Returns:
            The dimensions as a string.
        """
        if node is None:
            return ""
        
        result = ""
        for child in node.children:
            if child is None:
                continue
            tag = child.tag if hasattr(child, 'tag') else ""
            if tag == "kDimensionRange":
                result += self._get_single_dimension_range(child)
            elif tag == "kDimensionScalar":
                result += self._get_dimension_scalar(child)
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
        for child in node.children:
            if child is None:
                continue
            tag = child.tag if hasattr(child, 'tag') else ""
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
        for child in node.children:
            if child is None:
                continue
            tag = child.tag if hasattr(child, 'tag') else ""
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
        if node is None:
            return ""
        
        result = ""
        for child in node.children:
            if child is None:
                continue
            tag = child.tag if hasattr(child, 'tag') else ""
            if tag == "kDeclarationDimensions":
                result += self._get_dimension_text(child)
            elif tag == "kDimensionRange":
                result += self._get_single_dimension_range(child)
            elif tag == "kDimensionScalar":
                result += self._get_dimension_scalar(child)
        
        return result
    
    def _get_data_type(self, port_decl) -> str:
        """Extract data type from a port declaration.
        
        Args:
            port_decl: A kPortDeclaration node.
            
        Returns:
            The data type as a string (e.g., "logic", "op", or interface name).
        """
        data_type = port_decl.find({"tag": "kDataType"})
        if data_type is None:
            return ""
        
        # Check for primitive type (logic, bit, etc.)
        primitive = data_type.find({"tag": "kDataTypePrimitive"})
        if primitive:
            type_token = primitive.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
            if type_token:
                return self._get_text(type_token)
            # Try to find logic, bit, etc. directly
            for child in primitive.children:
                if child and hasattr(child, 'tag') and child.tag in ("logic", "bit", "reg", "wire"):
                    return child.tag
        
        # Check for interface port header (intf.master, intf.slave)
        interface_header = data_type.find({"tag": "kInterfacePortHeader"})
        if interface_header:
            return self._get_interface_port_type(interface_header)
        
        # Check for local root (user-defined type like "op")
        local_root = data_type.find({"tag": "kLocalRoot"})
        if local_root:
            unqualified_id = local_root.find({"tag": "kUnqualifiedId"})
            if unqualified_id:
                type_id = unqualified_id.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
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
            for child in unqualified_id.children:
                if child and hasattr(child, 'tag') and child.tag in ("SymbolIdentifier", "EscapedIdentifier"):
                    result.append(self._get_text(child))
        
        # Get modport if present
        for child in interface_header.children:
            if child and hasattr(child, 'tag') and child.tag == "SymbolIdentifier":
                result.append(self._get_text(child))
        
        return result
    
    def _get_port_direction(self, port_decl) -> str:
        """Extract port direction from a port declaration.
        
        Args:
            port_decl: A kPortDeclaration node.
            
        Returns:
            The direction as a string (input, output, inout, or "" for interface).
        """
        for child in port_decl.children:
            if child and hasattr(child, 'tag') and child.tag in ("input", "output", "inout"):
                return child.tag
        return ""
    
    def _get_port_name(self, port_decl) -> str:
        """Extract port name from a port declaration.
        
        Args:
            port_decl: A kPortDeclaration node.
            
        Returns:
            The port name as a string.
        """
        unqualified_id = port_decl.find({"tag": "kUnqualifiedId"})
        if unqualified_id:
            name_id = unqualified_id.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
            if name_id:
                return self._get_text(name_id)
        return ""
    
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
        data_type = self._get_data_type(port_decl)
        
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
    
    def _parse_parameter(self, param_decl) -> tuple:
        """Parse a single parameter declaration.
        
        Args:
            param_decl: A kParamDeclaration node.
            
        Returns:
            A tuple representing the parameter information (name, value, type, packed_dim).
        """
        param_type = param_decl.find({"tag": "kParamType"})
        
        data_type = "None"
        packed_dim = ""
        name = ""
        value = ""
        
        if param_type:
            # Get type info
            type_info = param_type.find({"tag": "kTypeInfo"})
            if type_info:
                for child in type_info.children:
                    if child and hasattr(child, 'tag') and child.tag in ("logic", "bit", "reg", "wire"):
                        data_type = child.tag
                        break
                # Check for user-defined type in kUnqualifiedId
                unqual_id = type_info.find({"tag": "kUnqualifiedId"})
                if unqual_id:
                    type_id = unqual_id.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
                    if type_id:
                        data_type = self._get_text(type_id)
            
            # Get packed dimensions
            packed_node = param_type.find({"tag": "kPackedDimensions"})
            if packed_node:
                packed_dim = self._get_packed_dimensions(packed_node)
            
            # Get parameter name
            name_id = param_type.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
            if name_id:
                name = self._get_text(name_id)
        
        # Get default value
        trailing_assign = param_decl.find({"tag": "kTrailingAssign"})
        if trailing_assign:
            expr = trailing_assign.find({"tag": "kExpression"})
            if expr:
                value = self._get_expression_text(expr)
        
        return (name, value, data_type, packed_dim)
    
    def _parse_localparam(self, param_decl) -> tuple:
        """Parse a single localparam declaration.
        
        Args:
            param_decl: A kParamDeclaration node with localparam keyword.
            
        Returns:
            A tuple representing the localparam information (name, value, type, packed_dim).
        """
        param_type = param_decl.find({"tag": "kParamType"})
        
        data_type = ""
        packed_dim = ""
        name = ""
        value = ""
        
        if param_type:
            # Get type info
            type_info = param_type.find({"tag": "kTypeInfo"})
            if type_info:
                for child in type_info.children:
                    if child and hasattr(child, 'tag') and child.tag in ("logic", "bit", "reg", "wire"):
                        data_type = child.tag
                        break
                # Check for user-defined type in kUnqualifiedId
                unqual_id = type_info.find({"tag": "kUnqualifiedId"})
                if unqual_id:
                    type_id = unqual_id.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
                    if type_id:
                        data_type = self._get_text(type_id)
            
            # Get packed dimensions
            packed_node = param_type.find({"tag": "kPackedDimensions"})
            if packed_node:
                packed_dim = self._get_packed_dimensions(packed_node)
            
            # Get parameter name
            name_id = param_type.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
            if name_id:
                name = self._get_text(name_id)
        
        # Get default value
        trailing_assign = param_decl.find({"tag": "kTrailingAssign"})
        if trailing_assign:
            expr = trailing_assign.find({"tag": "kExpression"})
            if expr:
                value = self._get_expression_text(expr)
        
        return (name, value, data_type, packed_dim)
    
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
                    # Check for primitive (only in direct children)
                    for child in dt_node.children:
                        if child and hasattr(child, 'tag') and child.tag == "kDataTypePrimitive":
                            for subchild in child.children:
                                if subchild and hasattr(subchild, 'tag') and subchild.tag in ("logic", "bit", "reg", "wire"):
                                    data_type = subchild.tag
                                    break
                            break
                    
                    # Check for user-defined type (only in direct children)
                    for child in dt_node.children:
                        if child and hasattr(child, 'tag') and child.tag == "kLocalRoot":
                            unqual_id = child.find({"tag": "kUnqualifiedId"})
                            if unqual_id:
                                type_id = unqual_id.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
                                if type_id:
                                    data_type = self._get_text(type_id)
                            break
                    
                    # Get packed dimensions (only in direct children)
                    for child in dt_node.children:
                        if child and hasattr(child, 'tag') and child.tag == "kPackedDimensions":
                            packed_dim = self._get_packed_dimensions(child)
                            break
            
            # Get signal name from kGateInstanceRegisterVariableList
            reg_var_list = inst_base.find({"tag": "kGateInstanceRegisterVariableList"})
            if reg_var_list:
                # Check for kRegisterVariable (for logic signals)
                reg_var = reg_var_list.find({"tag": "kRegisterVariable"})
                if reg_var:
                    name_id = reg_var.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
                    if name_id:
                        name = self._get_text(name_id)
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
                        
                        inst_name = gate_inst.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
                        if inst_name:
                            name = self._get_text(inst_name)
                        # Check for parentheses (interface instance)
                        has_paren = False
                        for gchild in gate_inst.children:
                            if gchild and hasattr(gchild, 'tag') and gchild.tag == "(":
                                has_paren = True
                                name += "("
                            elif gchild and hasattr(gchild, 'tag') and gchild.tag == ")":
                                name += ")"
                        # If no parentheses but it's an interface, add ()
                        if not has_paren and data_type and data_type.endswith("_if"):
                            name += "()"
        
        # Handle "None" values
        if not packed_dim:
            packed_dim = "None"
        if not unpacked_dim:
            unpacked_dim = "None"
        
        return (name, data_type, packed_dim, unpacked_dim)
    
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
        
        # Get data type (wire) from kDataType child
        dt_node = net_decl.find({"tag": "kDataType"})
        if dt_node:
            # Check for primitive type (wire, tri, etc.)
            for child in dt_node.children:
                if child and hasattr(child, 'tag') and child.tag in ("wire", "tri", "supply0", "supply1", "wand", "wor", "triand", "trior", "tri0", "tri1"):
                    data_type = child.tag
                    break
        
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
                name_id = net_var.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
                if name_id:
                    name = self._get_text(name_id)
                unpacked_node = net_var.find({"tag": "kUnpackedDimensions"})
                if unpacked_node:
                    unpacked_dim = self._get_unpacked_dimensions(unpacked_node)
        
        # Handle "None" values
        if not packed_dim:
            packed_dim = "None"
        if not unpacked_dim:
            unpacked_dim = "None"
        
        return (name, data_type, packed_dim, unpacked_dim)
    
    def _parse_import(self, import_decl) -> str:
        """Parse a single import declaration.
        
        Args:
            import_decl: A kPackageImportItem node.
            
        Returns:
            A string representing the import (e.g., "pkg_mthc_::*").
        """
        result = ""
        for child in import_decl.children:
            if child is None:
                continue
            tag = child.tag if hasattr(child, 'tag') else ""
            if tag == "kScopePrefix":
                # Get package name from kScopePrefix
                for subchild in child.children:
                    if subchild is None:
                        continue
                    subtag = subchild.tag if hasattr(subchild, 'tag') else ""
                    if subtag in ("SymbolIdentifier", "EscapedIdentifier"):
                        result += self._get_text(subchild)
                    elif subtag == "::":
                        result += "::"
            elif tag == "::":
                result += "::"
            elif tag == "*":
                result += "*"
            elif tag == "kUnqualifiedId":
                # Get package name from kUnqualifiedId (for specific imports)
                for subchild in child.children:
                    if subchild and hasattr(subchild, 'tag') and subchild.tag in ("SymbolIdentifier", "EscapedIdentifier"):
                        result += self._get_text(subchild)
        
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
        
        # Find module declaration
        module = self.syntax_data.tree.find({"tag": "kModuleDeclaration"})
        if module is None:
            return {}
        
        result = {
            'name': '',
            'package': [],
            'para': [],
            'lpara': [],
            'port': [],
            'signal': [],
            'import': []
        }
        
        # Get module name
        header = module.find({"tag": "kModuleHeader"})
        if header:
            name_id = header.find({"tag": ["SymbolIdentifier", "EscapedIdentifier"]})
            if name_id:
                result['name'] = self._get_text(name_id)
            
            # Get parameters from header
            for param in header.iter_find_all({"tag": "kParamDeclaration"}):
                result['para'].append(self._parse_parameter(param))
            
            # Get ports
            for port in header.iter_find_all({"tag": "kPortDeclaration"}):
                result['port'].append(self._parse_port_declaration(port))
        
        # Get imports from module body
        for import_decl in module.iter_find_all({"tag": "kPackageImportItem"}):
            import_str = self._parse_import(import_decl)
            if import_str:
                result['import'].append(import_str)
        
        # Get localparameters and parameters from module body
        # Note: verible uses kParamDeclaration for both parameter and localparam
        # We need to check the first child to determine which one
        for param_decl in module.iter_find_all({"tag": "kParamDeclaration"}):
            # Skip if already in header (parent is kFormalParameterList)
            parent = param_decl.parent
            if parent and hasattr(parent, 'tag') and parent.tag == "kFormalParameterList":
                continue
            
            # Check if it's localparam or parameter
            is_localparam = False
            for child in param_decl.children:
                if child and hasattr(child, 'tag') and child.tag == "localparam":
                    is_localparam = True
                    break
            
            if is_localparam:
                result['lpara'].append(self._parse_localparam(param_decl))
            else:
                result['para'].append(self._parse_parameter(param_decl))
        
        # Collect all signal declarations with their source position for ordering
        signal_entries = []
        
        # Get data declarations (signals)
        for data_decl in module.iter_find_all({"tag": "kDataDeclaration"}):
            # Skip if parent is kModuleHeader (it's a port declaration)
            parent = data_decl.parent
            if parent and hasattr(parent, 'tag') and parent.tag == "kModuleHeader":
                continue
            signal_info = self._parse_data_declaration(data_decl)
            # Skip empty signals (module instantiations)
            if signal_info[0]:
                pos = data_decl.start if data_decl.start is not None else 0
                signal_entries.append((pos, signal_info))
        
        # Get net declarations (wire declarations)
        for net_decl in module.iter_find_all({"tag": "kNetDeclaration"}):
            signal_info = self._parse_net_declaration(net_decl)
            if signal_info[0]:
                pos = net_decl.start if net_decl.start is not None else 0
                signal_entries.append((pos, signal_info))
        
        # Sort by source position to maintain original order
        signal_entries.sort(key=lambda x: x[0])
        result['signal'] = [info for _, info in signal_entries]
        
        self.module_info = result
        return result


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