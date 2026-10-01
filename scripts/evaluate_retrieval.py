"""Measures whether consistent pseudonymisation actually preserves
retrieval quality better than naive "redact everything to one fixed
placeholder" redaction — the project's central framing claim, which was
previously unmeasured.

Three variants of the same 24-document corpus (tests/data/retrieval_cases.py):
  - original:  no redaction at all (the ceiling)
  - naive:     every PERSON span -> the literal string "[REDACTED]"
  - pipeline:  this project's real pipeline.redact_document()

Naive and pipeline redaction deliberately share the exact same detector and
the exact same detected spans (PresidioNERDetector) — only the replacement
strategy differs (one fixed token for everyone vs a distinct, consistent
token per person). That isolates the thing actually under test: does the
*transformation* decision affect retrieval, holding detection constant?

For each variant, 24 queries (held constant, never redacted — a user's
question is not a stored document) are embedded with
sentence-transformers/all-MiniLM-L6-v2 and ranked against that variant's 24
document embeddings by cosine similarity. Reported per variant: top-1
accuracy, Mean Reciprocal Rank, and mean cosine similarity of each
variant's document embedding to that same document's ORIGINAL embedding
(how much the redaction moved the document in embedding space).

Nothing in RETRIEVAL_RESULTS.md is invented — it is this script's printed
output, copied in, same discipline as EVAL_RESULTS.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentence_transformers import SentenceTransformer, util  # noqa: E402

from pii_redaction.detectors.ner import PresidioNERDetector  # noqa: E402
from pii_redaction.pipeline import redact_document  # noqa: E402
from tests.data.retrieval_cases import RETRIEVAL_DOCS, RETRIEVAL_QUERIES  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parent.parent / "RETRIEVAL_RESULTS.md"
MODEL_NAME = "all-MiniLM-L6-v2"


def naive_redact(text: str, detector: PresidioNERDetector) -> str:
    """Every PERSON span -> the same fixed placeholder, regardless of which
    person. Uses the identical detector/spans as the real pipeline so the
    only variable is the replacement strategy, not detection quality."""
    spans = sorted(
        (s for s in detector.detect(text) if s.entity_type.value == "PERSON"),
        key=lambda s: s.start,
    )
    pieces, cursor = [], 0
    for s in spans:
        pieces.append(text[cursor : s.start])
        pieces.append("[REDACTED]")
        cursor = s.end
    pieces.append(text[cursor:])
    return "".join(pieces)


def build_variants() -> dict[str, list[str]]:
    detector = PresidioNERDetector()
    original = list(RETRIEVAL_DOCS)
    naive = [naive_redact(doc, detector) for doc in RETRIEVAL_DOCS]
    pipeline = [redact_document(doc)[0] for doc in RETRIEVAL_DOCS]
    return {"original": original, "naive": naive, "pipeline": pipeline}


def evaluate_variant(
    model: SentenceTransformer,
    query_embeddings,
    doc_texts: list[str],
    original_embeddings,
) -> dict:
    doc_embeddings = model.encode(doc_texts, convert_to_tensor=True, normalize_embeddings=True)
    sims = util.cos_sim(query_embeddings, doc_embeddings)  # [n_queries, n_docs]

    reciprocal_ranks = []
    top1_hits = []
    per_query = []
    for i, (query, correct_idx) in enumerate(RETRIEVAL_QUERIES):
        scores = sims[i]
        ranked = sorted(range(len(doc_texts)), key=lambda j: -scores[j])
        rank = ranked.index(correct_idx) + 1  # 1-indexed
        reciprocal_ranks.append(1.0 / rank)
        top1_hits.append(rank == 1)
        per_query.append(
            {"query": query, "correct_idx": correct_idx, "rank": rank, "top1": rank == 1}
        )

    doc_vs_original_sim = util.cos_sim(doc_embeddings, original_embeddings).diagonal().tolist()

    return {
        "top1_accuracy": sum(top1_hits) / len(top1_hits),
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks),
        "mean_sim_to_original": sum(doc_vs_original_sim) / len(doc_vs_original_sim),
        "per_query": per_query,
    }


def subset_metrics(per_query: list[dict], indices: range) -> dict:
    subset = [q for q in per_query if q["correct_idx"] in indices]
    return {
        "top1_accuracy": sum(q["top1"] for q in subset) / len(subset),
        "mrr": sum(1.0 / q["rank"] for q in subset) / len(subset),
    }


def main() -> None:
    model = SentenceTransformer(MODEL_NAME)
    variants = build_variants()

    query_texts = [q for q, _ in RETRIEVAL_QUERIES]
    query_embeddings = model.encode(query_texts, convert_to_tensor=True, normalize_embeddings=True)
    original_embeddings = model.encode(variants["original"], convert_to_tensor=True, normalize_embeddings=True)

    results = {}
    for name, docs in variants.items():
        results[name] = evaluate_variant(model, query_embeddings, docs, original_embeddings)

    SINGLE_PERSON = range(0, 16)
    MULTI_PERSON = range(16, 24)

    lines = [
        "# Retrieval-Quality Evaluation Results",
        "",
        f"Generated by `scripts/evaluate_retrieval.py` using `{MODEL_NAME}` "
        f"against the 24-document corpus in `tests/data/retrieval_cases.py` "
        f"(16 single-person + 8 multi-person documents, 24 queries, one per "
        f"document). Nothing here is estimated — this is the script's own output.",
        "",
        "## Overall",
        "",
        "| Variant | Top-1 accuracy | MRR | Mean cosine sim. to original |",
        "|---|---|---|---|",
    ]
    for name in ("original", "naive", "pipeline"):
        r = results[name]
        lines.append(
            f"| {name} | {r['top1_accuracy']:.3f} | {r['mrr']:.3f} | {r['mean_sim_to_original']:.3f} |"
        )

    lines += [
        "",
        "## By document type",
        "",
        "Naive and pipeline redaction are expected to look similar on "
        "single-person documents (both produce an internally consistent, "
        "repeated token there) and to diverge on multi-person documents, "
        "where naive redaction collapses two different people into the "
        "identical \"[REDACTED]\" string and pipeline redaction keeps them "
        "distinct as PERSON_A / PERSON_B.",
        "",
        "| Variant | Single-person top-1 | Single-person MRR | Multi-person top-1 | Multi-person MRR |",
        "|---|---|---|---|---|",
    ]
    for name in ("original", "naive", "pipeline"):
        single = subset_metrics(results[name]["per_query"], SINGLE_PERSON)
        multi = subset_metrics(results[name]["per_query"], MULTI_PERSON)
        lines.append(
            f"| {name} | {single['top1_accuracy']:.3f} | {single['mrr']:.3f} | "
            f"{multi['top1_accuracy']:.3f} | {multi['mrr']:.3f} |"
        )

    lines += ["", "## Per-query detail (pipeline variant)", "", "| Query | Correct doc | Rank | Hit? |", "|---|---|---|---|"]
    for q in results["pipeline"]["per_query"]:
        lines.append(f"| {q['query']} | {q['correct_idx']} | {q['rank']} | {'yes' if q['top1'] else 'no'} |")

    report = "\n".join(lines) + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(report)
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
