# Gold set

- `ci_dev.csv` is a **synthetic** labeled file used by CI. It is not a sample of city records.
- The real ~600-name queue is created with `oh label --sample-from data/derived/nyc/parcels_classified.parquet`.
- That queue (`queue.csv`) and any file under `individuals/` stay local. Do not commit them: they include personal names and address-like LLC strings.
- Label with `oh label`. Accepted classes are the `OwnerClass` values.
- `oh eval --gold eval/gold/queue.csv --split test` is what produces a real confusion matrix. Until that file is labeled, corrected headline shares are not computed.
