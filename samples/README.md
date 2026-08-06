# Local Verification Samples

This directory is intended for local scanned question paper datasets used for manual verification during development.
The actual datasets are kept locally and are NOT committed to this repository.

## Recommended Local Structure

To perform local verification, organize your sample files using the structure below:

- `samples/mathematics/` (Scanned math sheets, integration pages, matrix sheets)
- `samples/physics/` (Scanned physics question papers, diagrams)
- `samples/chemistry/` (Organic reaction chains, inorganic comparison sheets)
- `samples/biology/` (Labeled biological diagrams)
- `samples/tables/` (Comparison tables, tabular data papers)
- `samples/diagrams/` (Circuit graphs, plot sketches)
- `samples/mixed/` (Multi-subject entry examinations)

## How to use

During development, you should copy real-world test cases into these folders and run the manual verification scripts (e.g. `tests/manual/verify_output.py`) to confirm accuracy before freezing features.
