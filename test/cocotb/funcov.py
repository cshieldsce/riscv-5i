# funcov.py: Small functional coverage helper for the cocotb testbenches.
# cocotb doesn't come with coverage bins, so this counts hits for every
# combination of a few named axes and reports the ones that never got hit.

from collections import Counter
from itertools import product


class Cross:
    def __init__(self, name, *axes):
        # Each axis is (axis_name, values). Values can be a list, dict or range.
        self.name = name
        self.axes = [(axis_name, list(values)) for axis_name, values in axes]
        self.hits = Counter()

    def all_bins(self):
        # Every combination of one value from each axis
        return list(product(*(values for _, values in self.axes)))

    def sample(self, *point):
        if len(point) != len(self.axes):
            raise ValueError(f"{self.name}: expected {len(self.axes)} values but got {point}")
        self.hits[tuple(point)] += 1

    def missing(self):
        return [b for b in self.all_bins() if self.hits[b] == 0]

    def percent(self):
        total = len(self.all_bins())
        return 100.0 * (total - len(self.missing())) / total

    def report(self, log):
        total = len(self.all_bins())
        missing_bins = self.missing()
        log.info(f"Coverage for {self.name}: {total - len(missing_bins)}/{total} bins ({self.percent():.1f}%)")

        # Only print the first 20 so a broken test doesn't flood the log
        axis_names = [axis_name for axis_name, _ in self.axes]
        for b in missing_bins[:20]:
            log.warning(f"Warning: Bin never hit: {dict(zip(axis_names, b))}")
        if len(missing_bins) > 20:
            log.warning(f"Warning: ...and {len(missing_bins) - 20} more")
