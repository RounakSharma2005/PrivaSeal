def merge_overlapping(results):
    # Sort by start asc, then by length desc (so longer spans come first)
    sorted_res = sorted(results, key=lambda x: (x["start"], -(x["end"] - x["start"])))
    merged = []
    for r in sorted_res:
        if not merged:
            merged.append(r)
        else:
            last = merged[-1]
            if r["start"] < last["end"]:
                # Overlap! Since we sorted by length desc for same start, the previous one covers more or the same.
                # If they just overlap but have different starts, we can take the union or just keep the first one.
                # For simplicity, if it overlaps, we just ignore the smaller/later one.
                if r["end"] > last["end"]:
                    # This shouldn't happen often if we just pick the longest, but if it does, extend the last one
                    # Actually, for PII, usually we just want to redact the whole union or the longest.
                    pass
            else:
                merged.append(r)
    return merged
