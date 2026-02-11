"""Core graph data structures and definitions."""
from .graph import DKGEdge, DKGNode, EdgeFlowType, EntityClass, RelationType
from .ir import *
from .provenance import Provenance

__all__ = [
    "DKGEdge",
    "DKGNode", 
    "EdgeFlowType",
    "EntityClass",
    "RelationType",
    "Provenance",
]
