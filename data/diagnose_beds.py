"""Finds out why so few beds get into the catalog. Run once and paste the output.
    cd data
    python diagnose_beds.py
"""
import os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = ["x"]
import prepare_abo_catalog as p

tar = os.path.join(HERE, "raw", "abo-listings.tar")
stages = collections.Counter()
types = collections.Counter()
nodes = collections.Counter()
samples = []
for row in p.read_listings(tar):
    name = p.en_value(row.get("item_name")) or ""
    paths = [str(n.get("node_name") or n.get("path") or "") for n in row.get("node") or []]
    low = name.lower()
    if "bed" not in low and not any("/beds" in x.lower() or "bed frame" in x.lower() for x in paths):
        continue
    if any(w in low for w in p.BED_EXCLUDE + ("bedding", "bedspread", "bed bath", "bedside", "bedroom set")):
        continue
    if not any(w in low for w in ("bed frame", "platform bed", "bed,", " bed ", "daybed", "bunk", "canopy bed")) and not low.endswith(" bed"):
        continue
    stages["1 looks like a bed by name"] += 1
    for x in paths: nodes[x] += 1
    for t in row.get("product_type") or []: types[str(t.get("value"))] += 1
    dims = row.get("item_dimensions") or {}
    w, l = p.dim_cm(dims, "width"), p.dim_cm(dims, "length")
    if not w or not l:
        stages["2 REJECTED: no width/length"] += 1
        if len(samples) < 4: samples.append(("no dims", name[:70], list(dims.keys())))
        continue
    if not (80 <= max(w, l) <= 260) or min(w, l) < 24:
        stages["3 REJECTED: size outside 80-260 cm"] += 1
        if len(samples) < 8: samples.append(("size", name[:70], round(w), round(l)))
        continue
    codes = row.get("color_code") or []
    if not (codes and str(codes[0]).startswith("#")):
        stages["4 REJECTED: no colour code"] += 1
        continue
    if not row.get("main_image_id"):
        stages["5 REJECTED: no image"] += 1
        continue
    stages["6 would be accepted"] += 1
for k in sorted(stages): print(k, stages[k])
print("product types:", types.most_common(6))
print("category paths:", nodes.most_common(6))
print("examples:", samples)
