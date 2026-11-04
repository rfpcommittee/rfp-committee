"""
Final RFP table: merges the BLEU, COMET and chrF++ result files into ONE table per language,
awards marks for each metric, and totals them.

Inputs (produced by the three separate scripts; each needs its "Max" column):
    sarvam_bleu_results.csv    -> column "Max(B1,B2)"
    sarvam_comet_results.csv   -> column "Max(C1,C2)"
    sarvam_chrf_results.csv    -> column "Max(F1,F2)"
A metric whose file is missing is skipped (its marks are left out of the total).

Marks are RE-COMPUTED here from the Max scores, so this file is the single place that
holds the rules:

  BLEU   Option A : >=70 ->12 | 60-<70 ->10 | 50-<60 ->6 | <50 ->0
         Option B : >=70 ->12 | below 70: 12 - ceil((70-BLEU)/10), floored at 0
         "best"   : the higher of A and B for each language
  COMET  : >=0.85 ->10 | 0.75-<0.85 ->7 | 0.65-<0.75 ->4 | <0.65 ->0
  chrF++ : >=75 ->5    | 65-<75 ->3     | <65 ->0
  (all slabs half-open on the unrounded score)

Usage:
    python rfp_final_table.py                       # BLEU Option A (default)
    python rfp_final_table.py --bleu_option B
    python rfp_final_table.py --bleu_option best
    python rfp_final_table.py --bidder "Sarvam" --out final_table.csv
"""
import argparse
import math
import os
import pandas as pd

BLEU_MAX = 12
COMET_MAX = 10
CHRF_MAX = 5


def bleu_a(b):
    return 12 if b >= 70 else 10 if b >= 60 else 6 if b >= 50 else 0


def bleu_b(b):
    return 12 if b >= 70 else max(0, 12 - math.ceil((70 - b) / 10))


def comet_marks(c):
    return 10 if c >= 0.85 else 7 if c >= 0.75 else 4 if c >= 0.65 else 0


def chrf_marks(f):
    return 5 if f >= 75 else 3 if f >= 65 else 0


def tidy(df, max_col, new_name, label="input"):
    df = df[~df["Target"].astype(str).str.upper().str.startswith("OVERALL")]
    if max_col not in df.columns:
        raise SystemExit(f"{label}: column '{max_col}' not found (columns: {list(df.columns)})")
    return df[["Target", max_col]].rename(columns={max_col: new_name})


def load(path, max_col, new_name):
    if not os.path.exists(path):
        print(f"[note] {path} not found - skipping this metric")
        return None
    return tidy(pd.read_csv(path), max_col, new_name, path)


def build_table(parts, bleu_option="A"):
    """parts: list of tidy frames (Target + 'Max BLEU' / 'Max COMET' / 'Max chrF++').
    Returns the final table including the OVERALL row."""
    df = parts[0]
    for p in parts[1:]:
        df = df.merge(p, on="Target", how="outer")

    rule = {"A": bleu_a, "B": bleu_b, "best": lambda b: max(bleu_a(b), bleu_b(b))}[bleu_option]

    mark_cols, max_total = [], 0
    if "Max BLEU" in df:
        df["BLEU Marks"] = df["Max BLEU"].apply(lambda v: rule(v) if pd.notna(v) else 0)
        mark_cols.append("BLEU Marks"); max_total += BLEU_MAX
    if "Max COMET" in df:
        df["COMET Marks"] = df["Max COMET"].apply(lambda v: comet_marks(v) if pd.notna(v) else 0)
        mark_cols.append("COMET Marks"); max_total += COMET_MAX
    if "Max chrF++" in df:
        df["chrF++ Marks"] = df["Max chrF++"].apply(lambda v: chrf_marks(v) if pd.notna(v) else 0)
        mark_cols.append("chrF++ Marks"); max_total += CHRF_MAX

    df["Total Marks"] = df[mark_cols].sum(axis=1)
    df["Max Marks"] = max_total

    # keep a sensible column order
    order = ["Target"]
    for m, k in (("Max BLEU", "BLEU Marks"), ("Max COMET", "COMET Marks"), ("Max chrF++", "chrF++ Marks")):
        order += [c for c in (m, k) if c in df.columns]
    df = df[order + ["Total Marks", "Max Marks"]]

    # summary row
    total = {"Target": "OVERALL (avg score / total marks)"}
    for c in df.columns:
        if c.startswith("Max ") and c != "Max Marks":
            total[c] = round(df[c].mean(), 4 if "COMET" in c else 2)
    for c in mark_cols + ["Total Marks", "Max Marks"]:
        total[c] = df[c].sum()
    return pd.concat([df, pd.DataFrame([total])], ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bleu", default="sarvam_bleu_results.csv")
    ap.add_argument("--comet", default="sarvam_comet_results.csv")
    ap.add_argument("--chrf", default="sarvam_chrf_results.csv")
    ap.add_argument("--bleu_option", choices=["A", "B", "best"], default="A",
                    help="which BLEU marking rule to use (default A)")
    ap.add_argument("--bidder", default="")
    ap.add_argument("--out", default="rfp_final_table.csv")
    args = ap.parse_args()

    parts = [load(args.bleu, "Max(B1,B2)", "Max BLEU"),
             load(args.comet, "Max(C1,C2)", "Max COMET"),
             load(args.chrf, "Max(F1,F2)", "Max chrF++")]
    parts = [p for p in parts if p is not None]
    if not parts:
        raise SystemExit("No result files found.")

    df = build_table(parts, args.bleu_option)

    df.to_csv(args.out, index=False)
    title = f"{args.bidder + ' - ' if args.bidder else ''}BLEU rule: Option {args.bleu_option}"
    print(f"\n{title}\n")
    print(df.to_string(index=False))
    t, m = df["Total Marks"].iloc[-1], df["Max Marks"].iloc[-1]
    print(f"\nFinal: {t:g} / {m:g}  =  {100 * t / m:.1f}%")
    print(f"Saved to {args.out}")


if __name__ == "__main__":
    main()
