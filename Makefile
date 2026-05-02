# VSON v1.0 — one-command verification

PY ?= python3
TOOLS = tools/penman/vson_penman.py
EXAMPLE_VSON = examples/throne_room.vson
EXAMPLE_TTL = examples/throne_room.ttl

.PHONY: all check test parse-ontology penman-roundtrip shacl deps cli-check clean

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
	@echo "==> VSON-P (Penman) → VSON-T (Turtle) compile + SHACL conformance"
	@$(PY) $(TOOLS) to-turtle $(EXAMPLE_VSON) > /tmp/throne_room.emitted.ttl
	@$(PY) -c "import rdflib, pyshacl; \
	d = rdflib.Graph(); d.parse('/tmp/throne_room.emitted.ttl', format='turtle'); \
	s = rdflib.Graph(); s.parse('shapes/vson-shapes.ttl', format='turtle'); \
	o = rdflib.Graph(); \
	[o.parse(f, format='turtle') for f in ('ontology/vso.ttl','ontology/rcc8.ttl','ontology/allen.ttl')]; \
	c, _, r = pyshacl.validate(d, shacl_graph=s, ont_graph=o, inference='rdfs', allow_warnings=True); \
	assert c, 'transpiled Turtle failed SHACL:\n' + r; \
	print(f'  OK emitted Turtle parses + conforms, triples={len(d)}')"

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

cli-check:
	@echo "==> Rust CLI: build + test"
	@cd cli && cargo build --release --quiet
	@cd cli && cargo test --quiet 2>&1 | tail -8
	@echo "==> Rust CLI: golden parity with Python reference (rdflib graph-iso)"
	@cli/target/release/vson convert p2t $(EXAMPLE_VSON) > /tmp/rust.ttl
	@$(PY) $(TOOLS) to-turtle $(EXAMPLE_VSON) > /tmp/py.ttl
	@$(PY) -c "import rdflib; \
	a = rdflib.Graph(); a.parse('/tmp/rust.ttl', format='turtle'); \
	b = rdflib.Graph(); b.parse('/tmp/py.ttl', format='turtle'); \
	assert sorted(map(str,a)) == sorted(map(str,b)), 'graph mismatch'; \
	print(f'  OK identical, triples={len(a)}')"

clean:
	rm -rf __pycache__ tests/__pycache__ tools/penman/__pycache__
	rm -f /tmp/throne_room.emitted.ttl /tmp/rust.ttl /tmp/py.ttl
	cd cli && cargo clean --quiet 2>/dev/null || true
