# Attributed fixtures

`ttc-bus-sample.csv` contains 20 real source rows selected from the official TTC bus CSV downloaded 5 November 2026. Selection is deterministic: initial rows, representative quality flags, the first repeated-payload pair and the last row. This intentionally small sample is not statistically representative. Values are not corrected or deduplicated.

`codes.csv` is the complete small official lookup (46 rows) from the same inspection. Published encoding issues remain visible. `manifest.json` records exact hashes, original source row positions and the selection/serialization method. `docs/source-manifest.json` records the full downloads' provenance. Reproduce the fixture with `scripts/profile_sources.py --write-fixture` and the verified original bundle.

Synthetic edge cases are generated in `tests/helpers.py` and labelled `synthetic_test`; they are not official observations. Some synthetic dates, categories and durations are deliberately invalid.

Source: [City of Toronto / TTC Bus Delay Data](https://open.toronto.ca/dataset/ttc-bus-delay-data/).

Contains information licensed under the [Open Government Licence – Toronto](https://open.toronto.ca/open-data-licence/). This project is independent of the City/TTC and does not imply endorsement.
