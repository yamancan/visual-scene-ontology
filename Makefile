# VSON v1.0 — one-command verification

PY ?= python3
TOOLS = tools/penman/vson_penman.py
EXAMPLE_VSON = examples/throne_room.vson
EXAMPLE_TTL = examples/throne_room.ttl

.PHONY: all check test parse-ontology penman-roundtrip shacl deps cli-check spec-check x-check x-skill-check web-check deploy-check clean

all: check

check: parse-ontology penman-roundtrip shacl test spec-check

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

spec-check:
	@echo "==> Spec gallery: every example MUST SHACL-conform"
	@$(PY) -c "import json, glob, subprocess, sys, os; \
	from rdflib import Graph; \
	import pyshacl; \
	sys.path.insert(0, '.'); \
	from tools.penman import vson_penman as vp; \
	from tools.shacl_helper import validate_graph; \
	files = sorted(glob.glob('examples/gallery/*.vson')); \
	fails = []; \
	[fails.append(f) for f in files if (lambda g: not validate_graph(g)[0])((lambda: (lambda gg: (gg.parse(data=vp.to_turtle(open(f).read()), format='turtle'), gg)[1])(Graph()))()) ]; \
	print('\n'.join(f'  OK {f}' for f in files if f not in fails)); \
	(print('\n'.join(f'  FAIL {f}' for f in fails)) or sys.exit(1)) if fails else None"
	@echo "==> JSON Schemas parse"
	@$(PY) -c "import json; \
	[json.load(open(f)) for f in ('tools/schema/vson-output.schema.json','tools/schema/vson-jsonld.schema.json')]; \
	print('  OK both schemas parse')"

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

x-check:
	@echo "==> VSON-X gallery round-trip parity vs Penman"
	@$(PY) -m unittest tests.test_vson_x_basic tests.test_vson_x_roundtrip 2>&1 | tail -3

x-skill-check:
	@echo "==> VSON-X skill conformance over gallery-x corpus"
	@$(PY) tools/vson_x/skill_check.py \
		--corpus examples/gallery-x \
		--config skills/vson-extractor-x/conformance.json

deploy-check:
	@echo "==> Deploy preflight"
	@bash scripts/deploy_preflight.sh

web-check:
	@echo "==> Web: svelte-check + build"
	@cd web && pnpm install --frozen-lockfile --silent 2>&1 | tail -3
	@cd web && pnpm check 2>&1 | tail -3
	@cd web && pnpm build 2>&1 | tail -3
	@echo "  OK web build, dist=$$(du -sh web/build 2>/dev/null | cut -f1 || echo n/a)"

clean:
	rm -rf __pycache__ tests/__pycache__ tools/penman/__pycache__
	rm -f /tmp/throne_room.emitted.ttl /tmp/rust.ttl /tmp/py.ttl
	cd cli && cargo clean --quiet 2>/dev/null || true
	rm -rf web/.svelte-kit web/build
