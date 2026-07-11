#!/usr/bin/env bash
set -euo pipefail

CATALOG_DIR="${CATALOG_DIR:-microWakeWordsV4}"
LABEL_PROCESSING="${LABEL_PROCESSING:-mww-processing}"
LABEL_DONE="${LABEL_DONE:-mww-added}"
LABEL_FAILED="${LABEL_FAILED:-mww-failed}"
EXTERNAL_ROOT="${TATER_WAKE_EXTERNAL_ROOT:-/Volumes/Untitled}"
DEFAULT_TRAINER_DIR="${TATER_WAKE_TRAINER_DIR:-${EXTERNAL_ROOT}/microWakeWord-Trainer-AppleSilicon}"
DEFAULT_TMP_ROOT="${TATER_WAKE_TMP_ROOT:-${EXTERNAL_ROOT}/tater-wake-tmp}"

ISSUE_NUMBER=""
SAFE_WORD=""
RAW_PHRASE=""

log() {
  printf "%s [tater-wake-word] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

prepare_external_storage() {
  if [[ ! -d "$EXTERNAL_ROOT" ]]; then
    echo "External wake-word volume is not mounted: $EXTERNAL_ROOT"
    echo "Mount the SD card or set TATER_WAKE_EXTERNAL_ROOT to the mounted volume."
    exit 1
  fi

  mkdir -p \
    "$DEFAULT_TMP_ROOT/tmp" \
    "$DEFAULT_TMP_ROOT/outputs" \
    "$DEFAULT_TMP_ROOT/repos" \
    "$DEFAULT_TMP_ROOT/cache/pip" \
    "$DEFAULT_TMP_ROOT/cache/xdg" \
    "$DEFAULT_TMP_ROOT/cache/huggingface" \
    "$DEFAULT_TMP_ROOT/cache/torch" \
    "$DEFAULT_TMP_ROOT/cache/nltk" \
    "$DEFAULT_TMP_ROOT/cache/matplotlib"

  export TMPDIR="$DEFAULT_TMP_ROOT/tmp"
  export PIP_CACHE_DIR="$DEFAULT_TMP_ROOT/cache/pip"
  export XDG_CACHE_HOME="$DEFAULT_TMP_ROOT/cache/xdg"
  export HF_HOME="$DEFAULT_TMP_ROOT/cache/huggingface"
  export TORCH_HOME="$DEFAULT_TMP_ROOT/cache/torch"
  export NLTK_DATA="$DEFAULT_TMP_ROOT/cache/nltk"
  export MPLCONFIGDIR="$DEFAULT_TMP_ROOT/cache/matplotlib"
}

ensure_label() {
  local name="$1" color="$2" description="$3"
  gh label create "$name" --color "$color" --description "$description" --force >/dev/null 2>&1 || true
}

comment_issue() {
  local body="$1"
  [[ -n "$ISSUE_NUMBER" ]] || return 0
  local body_file
  body_file="$(mktemp "$TMPDIR/tater-wake-comment.XXXXXX.md")"
  printf "%s\n" "$body" > "$body_file"
  gh issue comment "$ISSUE_NUMBER" --body-file "$body_file" >/dev/null 2>&1 || true
  rm -f "$body_file"
}

comment_wake_word_links() {
  local heading="$1"
  local json_url="$2"
  local model_url="$3"
  [[ -n "$ISSUE_NUMBER" ]] || return 0
  local body_file
  body_file="$(mktemp "$TMPDIR/tater-wake-comment.XXXXXX.md")"
  {
    printf "## %s\n\n" "$heading"
    printf "**Wake word:** \`%s\`\n\n" "$SAFE_WORD"
    printf '%s\n' "- [JSON package](${json_url})"
    printf '%s\n\n' "- [TFLite model](${model_url})"
    printf "Use the JSON package URL in Tater's satellite wake-word settings.\n"
  } > "$body_file"
  gh issue comment "$ISSUE_NUMBER" --body-file "$body_file" >/dev/null 2>&1 || true
  rm -f "$body_file"
}

mark_failed() {
  local message="$1"
  [[ -n "$ISSUE_NUMBER" ]] || return 0
  comment_issue "$message"
  gh issue edit "$ISSUE_NUMBER" --add-label "$LABEL_FAILED" --remove-label "$LABEL_PROCESSING" >/dev/null 2>&1 || true
}

on_error() {
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    mark_failed "Wake-word training failed for \`${SAFE_WORD:-unknown}\`. Check the workflow logs for details."
  fi
  exit "$rc"
}
trap on_error ERR

prepare_external_storage

if [[ -z "${GITHUB_EVENT_PATH:-}" || ! -f "${GITHUB_EVENT_PATH:-}" ]]; then
  echo "GITHUB_EVENT_PATH is required."
  exit 1
fi

request_env="$(mktemp "$TMPDIR/tater-wake-request.XXXXXX")"
python3 - <<'PY' "$GITHUB_EVENT_PATH" "$request_env"
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

event_path = Path(sys.argv[1])
env_path = Path(sys.argv[2])
event = json.loads(event_path.read_text(encoding="utf-8"))
issue = event.get("issue") if isinstance(event, dict) else {}
title = str(issue.get("title") or "")
number = str(issue.get("number") or "")
match = re.match(r"^\s*mww:\s*(.+?)\s*$", title, flags=re.I)

values = {
    "SHOULD_TRAIN": "0",
    "ISSUE_NUMBER": number,
    "RAW_PHRASE": "",
    "SAFE_WORD": "",
    "REQUEST_ERROR": "",
}

if match:
    phrase = match.group(1).strip()
    safe = re.sub(r"[^a-z0-9_]+", "", re.sub(r"\s+", "_", phrase.lower())).strip("_")
    values.update({"SHOULD_TRAIN": "1", "RAW_PHRASE": phrase, "SAFE_WORD": safe})
    if not safe:
        values["REQUEST_ERROR"] = "The wake-word request is empty after `mww:`."
    elif len(safe) < 2:
        values["REQUEST_ERROR"] = "The wake-word request is too short."
    elif len(safe) > 64:
        values["REQUEST_ERROR"] = "The wake-word request is too long. Keep it under 64 slug characters."

env_path.write_text(
    "".join(f"{key}={shlex.quote(value)}\n" for key, value in values.items()),
    encoding="utf-8",
)
PY

# shellcheck disable=SC1090
source "$request_env"
rm -f "$request_env"

if [[ "$SHOULD_TRAIN" != "1" ]]; then
  log "Issue title does not start with mww:. Nothing to do."
  exit 0
fi

ensure_label "$LABEL_PROCESSING" "fb923c" "Wake-word training is running"
ensure_label "$LABEL_DONE" "2da44e" "Wake word was generated and added"
ensure_label "$LABEL_FAILED" "d73a4a" "Wake-word training failed or needs attention"

if [[ -n "$REQUEST_ERROR" ]]; then
  mark_failed "$REQUEST_ERROR"
  exit 0
fi

mkdir -p "$CATALOG_DIR"
json_path="$CATALOG_DIR/$SAFE_WORD.json"
tflite_path="$CATALOG_DIR/$SAFE_WORD.tflite"

if [[ -f "$json_path" && -f "$tflite_path" ]]; then
  log "Wake word already exists: $SAFE_WORD"
  python3 scripts/generate_wake_word_manifest.py
  raw_base="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/main"
  comment_wake_word_links "Wake Word Already Exists" "${raw_base}/${json_path}" "${raw_base}/${tflite_path}"
  gh issue edit "$ISSUE_NUMBER" --add-label "$LABEL_DONE" --remove-label "$LABEL_PROCESSING" >/dev/null 2>&1 || true
  gh issue close "$ISSUE_NUMBER" >/dev/null 2>&1 || true
  exit 0
fi

gh issue edit "$ISSUE_NUMBER" --add-label "$LABEL_PROCESSING" --remove-label "$LABEL_FAILED" >/dev/null 2>&1 || true

trainer_dir="$DEFAULT_TRAINER_DIR"
if [[ ! -x "$trainer_dir/train_microwakeword_macos.sh" ]]; then
  if [[ "$trainer_dir" == "${EXTERNAL_ROOT}/"* && ! -e "$trainer_dir" ]]; then
    mkdir -p "$(dirname "$trainer_dir")"
    gh repo clone TaterTotterson/microWakeWord-Trainer-AppleSilicon "$trainer_dir"
  else
    echo "Trainer script not found at: $trainer_dir"
    echo "Set TATER_WAKE_TRAINER_DIR to an external-volume trainer checkout."
    exit 1
  fi
fi

if [[ ! -x "$trainer_dir/train_microwakeword_macos.sh" ]]; then
  echo "Trainer script not found at: $trainer_dir"
  exit 1
fi

output_dir="$DEFAULT_TMP_ROOT/outputs/$SAFE_WORD"
rm -rf "$output_dir"
mkdir -p "$output_dir"

log "Training '$RAW_PHRASE' as '$SAFE_WORD' with $trainer_dir"
log "Using external temp root: $DEFAULT_TMP_ROOT"
(
  cd "$trainer_dir"
  TMPDIR="$TMPDIR" TRAINED_WAKE_WORDS_DIR="$output_dir" ./train_microwakeword_macos.sh "$SAFE_WORD"
)

cp "$output_dir/$SAFE_WORD.json" "$json_path"
cp "$output_dir/$SAFE_WORD.tflite" "$tflite_path"

python3 - <<'PY' "$json_path"
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
data["website"] = "https://github.com/TaterTotterson/Tater-Wake-Words"
path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

python3 scripts/generate_wake_word_manifest.py

git add "$json_path" "$tflite_path" wake_word_manifest.json
if git diff --cached --quiet; then
  log "No catalog changes to commit."
else
  git commit -m "Add wake word: $SAFE_WORD"
  git push
fi

raw_base="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/main"
comment_wake_word_links "Wake Word Added" "${raw_base}/${json_path}" "${raw_base}/${tflite_path}"
gh issue edit "$ISSUE_NUMBER" --add-label "$LABEL_DONE" --remove-label "$LABEL_PROCESSING" >/dev/null 2>&1 || true
gh issue close "$ISSUE_NUMBER" >/dev/null 2>&1 || true
log "Completed issue #$ISSUE_NUMBER for $SAFE_WORD"
