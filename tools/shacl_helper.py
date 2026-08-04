"""
Shared SHACL validation primitive.

The baseline measurement holds an in-memory rdflib.Graph after Penman→Turtle;
the test suite holds a path on disk. Both call validate_graph; the path-based
form is a thin wrapper.
"""

from __future__ import annotations

import os
from typing import Tuple

import pyshacl
import rdflib

from tools import resource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ONTOLOGY_FILES = (
    "ontology/vso.ttl",
    "ontology/rcc8.ttl",
    "ontology/allen.ttl",
)
SHAPES_FILE = "shapes/vson-shapes.ttl"


def _load_ontology() -> rdflib.Graph:
    g = rdflib.Graph()
    for f in ONTOLOGY_FILES:
        g.parse(resource(f), format="turtle")
    return g


def _load_shapes() -> rdflib.Graph:
    g = rdflib.Graph()
    g.parse(resource(SHAPES_FILE), format="turtle")
    return g


def validate_graph(data: rdflib.Graph) -> Tuple[bool, str]:
    """Validate an in-memory data graph against the VSON shapes + ontology.

    Returns (conforms, report_text).
    """
    conforms, _, report_text = pyshacl.validate(
        data,
        shacl_graph=_load_shapes(),
        ont_graph=_load_ontology(),
        inference="rdfs",
        abort_on_first=False,
        allow_warnings=True,
    )
    return conforms, report_text


def validate_path(data_path: str) -> Tuple[bool, str]:
    """Convenience wrapper: parse a Turtle file from disk and validate it."""
    data = rdflib.Graph()
    data.parse(os.path.join(ROOT, data_path), format="turtle")
    return validate_graph(data)
