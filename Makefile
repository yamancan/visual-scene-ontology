# VSON v1.0 — one-command verification

PY ?= python3
TOOLS = tools/penman/vson_penman.py
EXAMPLE_VSON = examples/throne_room.vson
EXAMPLE_TTL = examples/throne_room.ttl

.PHONY: all check test parse-ontology penman-roundtrip shacl deps clean

all: check

check: parse-ontology penman-roundtrip shacl test

deps:
	$(PY) -m pip install --user --quiet rdflib pyshacl

parse-ontology:
	@echo "==> Parsing ontology, shapes, and example with rdflib"
	@$(PY) -c "import rdflib; \
	files = ['ontology/vso.ttl','ontology/rcc8.ttl','ontology/allen.ttl', \
	         'shapes/vson-shapes.ttl','examples/throne_room.ttl']; \
	[print(f'  OK {f}  triples={len(rdflib.Graph().parse(f, format=\"turtle\"))}') for f in files]"

penman-roundtrip:
	@echo "==> VSON-P (Penman) → VSON-T (Turtle) compile"
	@$(PY) $(TOOLS) to-turtle $(EXAMPLE_VSON) > /tmp/throne_room.emitted.ttl
	@$(PY) -c "import rdflib; g = rdflib.Graph(); g.parse('/tmp/throne_room.emitted.ttl', format='turtle'); \
	print(f'  OK emitted Turtle parses, triples={len(g)}')"

shacl:
	@echo "==> SHACL conformance"
	@$(PY) -c "import rdflib, pyshacl; \
	d = rdflib.Graph(); d.parse('$(EXAMPLE_TTL)', format='turtle'); \
	s = rdflib.Graph(); s.parse('shapes/vson-shapes.ttl', format='turtle'); \
	o = rdflib.Graph(); \
	[o.parse(f, format='turtle') for f in ('ontology/vso.ttl','ontology/rcc8.ttl','ontology/allen.ttl')]; \
	c, _, r = pyshacl.validate(d, shacl_graph=s, ont_graph=o, inference='rdfs', allow_warnings=True); \
	print('  ' + ('CONFORMS' if c else 'FAILED:\n' + r))"

test:
	@echo "==> Test suite"
	@$(PY) -m unittest discover -s tests

clean:
	rm -rf __pycache__ tests/__pycache__ tools/penman/__pycache__
	rm -f /tmp/throne_room.emitted.ttl
