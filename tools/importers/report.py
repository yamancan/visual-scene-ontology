"""The lossiness report — what an import kept, bent, and threw away.

An importer that only writes VSON hides its own arithmetic. Every conversion
here is accompanied by a JSON report with one rule: **every source construct is
counted exactly once**, under ``exact``, ``approximate`` or ``dropped``, and a
dropped one carries the reason. Nothing is silently skipped, which is the same
discipline docs/vson.md §5.13.6 imposes on the geometry check's verdicts.

The report is a plain dict with sorted keys, so it diffs cleanly and can be
frozen as a golden file beside the VSON it describes.
"""

from __future__ import annotations

import collections


class Counter(object):
    """Counts of one construct family, by outcome and by source name."""

    def __init__(self):
        self.by_outcome = collections.Counter()
        self.by_name = collections.defaultdict(collections.Counter)
        self.unmapped = collections.Counter()
        self.reasons = collections.Counter()

    def record(self, name, fidelity, reason=None):
        self.by_outcome[fidelity] += 1
        self.by_name[fidelity][name] += 1
        if reason:
            self.reasons[reason] += 1

    def record_unmapped(self, name):
        self.by_outcome["unmapped"] += 1
        self.unmapped[name] += 1

    def to_dict(self):
        return {
            "read": sum(self.by_outcome.values()),
            "exact": self.by_outcome["exact"],
            "approximate": self.by_outcome["approximate"],
            "dropped": self.by_outcome["dropped"],
            "unmapped": self.by_outcome["unmapped"],
            "by_name": {
                outcome: dict(sorted(counts.items()))
                for outcome, counts in sorted(self.by_name.items())
            },
            "unmapped_names": dict(sorted(self.unmapped.items())),
            "drop_reasons": dict(sorted(self.reasons.items())),
        }


class LossinessReport(object):
    """One report per input file, whatever the dataset."""

    def __init__(self, dataset, source, table_path, importer_version, policy):
        self.dataset = dataset
        self.source = source
        self.table_path = table_path
        self.importer_version = importer_version
        self.policy = dict(policy)
        self.records = 0
        self.scenes = 0
        self.skipped_records = collections.Counter()
        self.entities = collections.Counter()
        self.traits = collections.Counter()
        self.geometry = collections.Counter()
        self.predicates = Counter()
        self.attributes = Counter()
        self.directionals = collections.Counter()
        self.notes = []

    def note(self, text):
        if text not in self.notes:
            self.notes.append(text)

    def to_dict(self):
        return {
            "importer": "tools.importers",
            "importer_version": self.importer_version,
            "dataset": self.dataset,
            "source": self.source,
            "mapping_table": self.table_path,
            "policy": dict(sorted(self.policy.items())),
            "records_read": self.records,
            "scenes_emitted": self.scenes,
            "records_skipped": dict(sorted(self.skipped_records.items())),
            "entities": dict(sorted(self.entities.items())),
            "traits": dict(sorted(self.traits.items())),
            "geometry": dict(sorted(self.geometry.items())),
            "predicates": self.predicates.to_dict(),
            "attributes": self.attributes.to_dict(),
            "directionals": dict(sorted(self.directionals.items())),
            "notes": list(self.notes),
        }
