#!/usr/bin/env bash
#
# Rebuild the error cards from scratch.
#
#   ./rebuild.sh                 full rebuild, including the source download
#   ./rebuild.sh --no-download   rebuild cards from sources already on disk
#   ./rebuild.sh --refresh       re-query SciPost even if the cache exists
#   ./rebuild.sh --precutoff     also build the pre-2022-11-30 dataset, whose
#                                referee text predates ChatGPT's release
#
# Safe to interrupt and re-run: every stage skips work already done, and the
# arXiv download resumes rather than starting over.
#
# Needs: python3.10+, ~2.5 GB of disk, and a few hours for the first run.

set -euo pipefail
cd "$(dirname "$0")"

CACHE=data/scipost_api_cache
SOURCES=data/scipost_sources
CANDIDATES=data/scipost_candidates.jsonl
MANIFEST=data/fetch_manifest.jsonl

DOWNLOAD=yes
REFRESH=no
PRECUTOFF=no
CUTOFF=2022-11-30
for arg in "$@"; do
  case "$arg" in
    --no-download) DOWNLOAD=no ;;
    --refresh)     REFRESH=yes ;;
    --precutoff)   PRECUTOFF=yes ;;
    -h|--help)     sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# --- 0. environment ----------------------------------------------------------
step "Python environment"
if [ ! -x .venv/bin/python ]; then
  echo "creating .venv"
  python3 -m venv .venv
fi
./.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
PY=./.venv/bin/python
echo "using $($PY --version) in .venv"

# --- 1. SciPost -------------------------------------------------------------
# One pass over the public API, cached to disk. Everything after this is
# offline, so the selection rules can be re-run freely.
step "SciPost submissions (about 6 minutes, ~75 MB)"
if [ "$REFRESH" = yes ] || [ ! -d "$CACHE" ]; then
  $PY scipost_mine.py enumerate --cache-dir "$CACHE"
else
  echo "cache present at $CACHE — skipping (use --refresh to re-query)"
fi

# --- 2. candidates ----------------------------------------------------------
# Deterministic rules only: no model decides what enters the dataset.
step "Selecting candidates"
$PY scipost_mine.py select --cache-dir "$CACHE" --output "$CANDIDATES"

# --- 3. arXiv sources -------------------------------------------------------
# Each review round names its own arXiv version pair; 59% are not v1 -> v2.
step "arXiv source pairs"
$PY scipost_mine.py fetch-manifest --candidates "$CANDIDATES" --output "$MANIFEST"
if [ "$DOWNLOAD" = yes ]; then
  echo "downloading to $SOURCES — a few hours on a first run, ~1.9 GB."
  echo "safe to interrupt: re-running this script resumes where it stopped."
  $PY collect_arxiv_candidates.py fetch-sources \
      --input "$MANIFEST" \
      --output data/scipost_sources_status.jsonl \
      --source-dir "$SOURCES"
else
  echo "--no-download: using whatever is already in $SOURCES"
fi

# --- 4. cards ---------------------------------------------------------------
step "Building cards"
$PY build_error_cards.py --candidates "$CANDIDATES" --source-dir "$SOURCES" --output-dir data

# --- 5. ranking -------------------------------------------------------------
# Heuristic scoring. It reorders the queue; it never removes a card.
step "Ranking"
$PY rank_cards.py --gold data/error_cards_gold.jsonl \
                  --unresolved data/error_cards_unresolved.jsonl

# --- 6. pre-cutoff dataset --------------------------------------------------
# Same rules, restricted to referee reports written before ChatGPT was public,
# so the ground truth is human by construction. The filter is on the report
# date, not the paper's: a 2021 paper can be refereed in 2024.
if [ "$PRECUTOFF" = yes ]; then
  step "Pre-$CUTOFF dataset"
  mkdir -p data/precutoff
  $PY scipost_mine.py select --cache-dir "$CACHE" \
      --output data/precutoff_candidates.jsonl --reports-before "$CUTOFF"
  $PY build_error_cards.py --candidates data/precutoff_candidates.jsonl \
      --source-dir "$SOURCES" --output-dir data/precutoff
  $PY rank_cards.py --gold data/precutoff/error_cards_gold.jsonl \
                    --unresolved data/precutoff/error_cards_unresolved.jsonl
  echo "see data/precutoff/README.md"
fi

# --- done -------------------------------------------------------------------
step "Done"
cat <<'SUMMARY'
  data/error_cards.jsonl             benchmark cards — the ONLY file a model may see
  data/error_cards_gold.jsonl        the answers: referee quote, DOI, location
  data/error_cards_unresolved.jsonl  cards needing a human to localize
  data/error_cards_skipped.jsonl     papers whose sources could not be read

Counts will differ from the committed files: SciPost grows, so a later run
sees submissions that did not exist when these were built. That is expected,
not a regression.

Every card ships human_severity_label "unreviewed". A referee saying "wrong"
routes a paper to an expert; it does not certify the flaw is real or fatal.
SUMMARY
