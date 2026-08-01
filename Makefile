# VSON v1.3 — one-command verification

PY ?= python3
# The transpiler runs as a module (python -m) so package-relative imports
# resolve from the repo root — no sys.path juggling inside the sources.
TOOLS = -m tools.penman.vson_penman
EXAMPLE_VSON = examples/throne_room.vson
EXAMPLE_TTL = examples/throne_room.ttl

.PHONY: all check check-all test parse-ontology penman-roundtrip shacl owl-consistency deps lint-py cli-check spec-check iri-check x-check x-skill-check envelope-check web-check web-deploy web-smoke deploy-check site clean

all: check

check: parse-ontology penman-roundtrip shacl owl-consistency test spec-check lint-py iri-check

# Everything the CI runs, minus the web app (which needs pnpm/node).
check-all: check cli-check x-check x-skill-check envelope-check

# Installs the pinned dependency ranges declared in pyproject.toml and puts
# the `tools` package on sys.path (editable, so edits take effect immediately).
deps:
	$(PY) -m pip install --user --quiet -e .

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

owl-consistency:
	@echo "==> OWL 2 RL consistency (disjointness clashes the rdfs-SHACL gate cannot see)"
	@$(PY) -m tools.owlrl_check

test:
	@echo "==> Test suite"
	@$(PY) -m unittest discover -s tests

lint-py:
	@echo "==> Python lint (ruff: pyflakes + pycodestyle errors)"
	@$(PY) -m ruff check tools tests scripts

spec-check:
	@echo "==> Spec gallery: every example MUST SHACL-conform"
	@$(PY) -c "import json, glob, subprocess, sys, os; \
	from rdflib import Graph; \
	import pyshacl; \
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
	@echo "==> Rust CLI: fmt + clippy"
	@cd cli && cargo fmt --check
	@cd cli && cargo clippy --all-targets -- -D warnings
	@echo "==> Rust CLI: build + test"
	@cd cli && cargo build --release --quiet
	@cd cli && cargo test --quiet 2>&1 | tail -8
	@echo "==> Rust CLI: golden parity with Python reference (byte + graph-iso, throne_room + 16-scene gallery)"
	@$(PY) -m tools.parity_check --bytes cli/target/release/vson

x-check:
	@echo "==> VSON-X gallery round-trip parity vs Penman"
	@$(PY) -m unittest tests.test_vson_x_basic tests.test_vson_x_roundtrip 2>&1 | tail -3

x-skill-check:
	@echo "==> VSON-X skill conformance over gallery-x corpus"
	@$(PY) -m tools.vson_x.skill_check \
		--corpus examples/gallery-x \
		--config skills/vson-extractor-x/conformance.json

iri-check:
	@echo "==> Legacy IRI gate: the withdrawn namespace host MUST NOT reappear"
	@$(PY) scripts/check_legacy_iri.py

envelope-check:
	@echo "==> Studio envelope corpus: every committed envelope MUST SHACL-conform"
	@$(PY) scripts/envelope_check.py

deploy-check:
	@echo "==> Deploy preflight"
	@bash scripts/deploy_preflight.sh

web-check:
	@echo "==> Web: svelte-check + build"
	@cd web && pnpm install --frozen-lockfile --silent 2>&1 | tail -3
	@cd web && pnpm check 2>&1 | tail -3
	@cd web && pnpm build 2>&1 | tail -3
	@echo "  OK web build, dist=$$(du -sh web/build 2>/dev/null | cut -f1 || echo n/a)"

web-deploy:
	@echo "==> Web: build + browser smoke + manual Cloudflare Pages deploy (project vson-studio)"
	@cd web && pnpm install --frozen-lockfile --silent 2>&1 | tail -3
	@cd web && pnpm build 2>&1 | tail -3
	scripts/browser_smoke.sh web/build
	npx wrangler pages deploy web/build --project-name vson-studio

web-smoke:
	scripts/browser_smoke.sh web/build

site:
	@echo "==> Publish surface: assemble site/ from publish/ + the tracked sources"
	@$(PY) scripts/build_site.py

clean:
	find . -name __pycache__ -type d -not -path './web/node_modules/*' -exec rm -rf {} +
	rm -rf *.egg-info .ruff_cache
	rm -f /tmp/throne_room.emitted.ttl /tmp/rust.ttl /tmp/py.ttl
	cd cli && cargo clean --quiet 2>/dev/null || true
	rm -rf web/.svelte-kit web/build
