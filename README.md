# Datasets

## Catalog (Recommender layer) — ready to use
`filnow/furniture-synthetic-dataset` on HuggingFace (10k synthetic studio
product shots, apache-2.0). Columns: type, style, color, material, shape,
details, room_type, price_range. Good direct fit for `catalog_items` — needs
normalizing into the shape in `docs/CONTRACTS.md` section 2 (map `type` →
`category`, but note it only covers a narrow set of furniture types, so you
may still want to broaden category coverage with another catalog source or
by adding categories manually).

```python
from datasets import load_dataset
ds = load_dataset("filnow/furniture-synthetic-dataset")
```

## Still needed — Perception layer (NOT covered by the above)
The synthetic dataset is single-item studio photos on white backgrounds — it
has no room scenes, no bounding-box annotations, no empty-space labels. For
Perception you still need:

- **Room-scene photos with furniture detection annotations** — your synopsis
  names the COCO indoor-furniture subset and HomeObjects-3K specifically.
  Search & download those directly.
- **A room-style-labeled dataset** for the MobileNetV3 style classifier
  (search "indoor scene / room style classification dataset").

Ask me to search for and shortlist specific ones when Track A is ready to
start — I can pull current options with download links.
