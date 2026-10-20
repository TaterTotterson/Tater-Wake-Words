#!/usr/bin/env bash
set -euo pipefail

CATALOG_DIR="${CATALOG_DIR:-microWakeWordsV8}"
LABEL_PROCESSING="${LABEL_PROCESSING:-mww-processing}"
LABEL_DONE="${LABEL_DONE:-mww-added}"
LABEL_FAILED="${LABEL_FAILED:-mww-failed}"
EXTERNAL_ROOT="${TATER_WAKE_EXTERNAL_ROOT:-/Volumes/Untitled}"
DEFAULT_TRAINER_DIR="${TATER_WAKE_TRAINER_DIR:-${EXTERNAL_ROOT}/microWakeWord-Trainer-AppleSilicon}"
DEFAULT_TMP_ROOT="${TATER_WAKE_TMP_ROOT:-${EXTERNAL_ROOT}/tater-wake-tmp}"
REQUESTED_ISSUE_NUMBER="${WAKE_WORD_ISSUE_NUMBER:-}"
BOOTSTRAP_TMPDIR="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"

ISSUE_NUMBER=""
SAFE_WORD=""
RAW_PHRASE=""

log() {
  printf "%s [tater-wake-word] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

parse_request_event() {
  local event_path="$1"
  local request_env
  request_env="$(mktemp "$BOOTSTRAP_TMPDIR/tater-wake-request.XXXXXX")"
  python3 scripts/parse_wake_word_request.py "$event_path" "$request_env"
  # shellcheck disable=SC1090
  source "$request_env"
  rm -f "$request_env"
}

refresh_request_from_github() {
  local live_event
  live_event="$(mktemp "$BOOTSTRAP_TMPDIR/tater-wake-event.XXXXXX")"
  gh api "repos/${GITHUB_REPOSITORY}/issues/${ISSUE_NUMBER}" > "$live_event"
  parse_request_event "$live_event"
  rm -f "$live_event"
}

clear_processing_label() {
  [[ -n "$ISSUE_NUMBER" ]] || return 0
  gh issue edit "$ISSUE_NUMBER" --remove-label "$LABEL_PROCESSING" >/dev/null 2>&1 || true
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
  body_file="$(mktemp "${TMPDIR:-$BOOTSTRAP_TMPDIR}/tater-wake-comment.XXXXXX")"
  printf "%s\n" "$body" > "$body_file"
  gh issue comment "$ISSUE_NUMBER" --body-file "$body_file" >/dev/null 2>&1 || true
  rm -f "$body_file"
}

comment_wake_word_links() {
  local heading="$1"
  local bundle_url="$2"
  local esphome_json_url="$3"
  local mww_model_url="$4"
  local oww_model_url="$5"
  local nww_cnn_model_url="$6"
  local nww_gru_model_url="$7"
  [[ -n "$ISSUE_NUMBER" ]] || return 0
  local body_file
  body_file="$(mktemp "${TMPDIR:-$BOOTSTRAP_TMPDIR}/tater-wake-comment.XXXXXX")"
  {
    printf "## %s\n\n" "$heading"
    printf "**Wake word:** \`%s\`\n\n" "$SAFE_WORD"
    printf '%s\n' "- [Tater wake bundle](${bundle_url})"
    printf '%s\n' "- [MWW ESPHome JSON package](${esphome_json_url})"
    printf '%s\n' "- [MWW TFLite model](${mww_model_url})"
    printf '%s\n' "- [OWW ONNX model](${oww_model_url})"
    printf '%s\n' "- [NWW CNN ONNX model](${nww_cnn_model_url})"
    printf '%s\n\n' "- [NWW GRU ONNX model](${nww_gru_model_url})"
    printf "Use the wake bundle in Tater for MWW, OWW, NWW, or a supported dual-detector mode. Use the ESPHome JSON only with ESPHome micro_wake_word.\n"
  } > "$body_file"
  gh issue comment "$ISSUE_NUMBER" --body-file "$body_file" >/dev/null 2>&1 || true
  rm -f "$body_file"
}

bundle_package_valid() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

from scripts.generate_wake_word_manifest import bundle_model_fields

bundle_path = Path(sys.argv[1]).resolve()
raise SystemExit(0 if bundle_model_fields(bundle_path) else 1)
PY
}

mark_failed() {
  local message="$1"
  [[ -n "$ISSUE_NUMBER" ]] || return 0
  comment_issue "$message"
  gh issue edit "$ISSUE_NUMBER" --add-label "$LABEL_FAILED" --remove-label "$LABEL_PROCESSING" >/dev/null 2>&1 || true
}

on_exit() {
  local rc=$?
  trap - EXIT
  if [[ $rc -ne 0 ]]; then
    mark_failed "Wake-word training failed for \`${SAFE_WORD:-unknown}\`. Check the workflow logs for details."
  fi
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ -z "${GITHUB_EVENT_PATH:-}" || ! -f "${GITHUB_EVENT_PATH:-}" ]]; then
  echo "GITHUB_EVENT_PATH is required."
  exit 1
fi

mkdir -p "$BOOTSTRAP_TMPDIR"
if [[ -n "$REQUESTED_ISSUE_NUMBER" ]]; then
  if [[ ! "$REQUESTED_ISSUE_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
    echo "WAKE_WORD_ISSUE_NUMBER must be a positive issue number."
    exit 1
  fi
  ISSUE_NUMBER="$REQUESTED_ISSUE_NUMBER"
else
  parse_request_event "$GITHUB_EVENT_PATH"
fi

if [[ -n "$ISSUE_NUMBER" ]]; then
  refresh_request_from_github
fi

if [[ "$SHOULD_TRAIN" != "1" ]]; then
  log "Issue is closed or no longer has a valid mww: title. Nothing to do."
  exit 0
fi

ensure_label "$LABEL_PROCESSING" "fb923c" "Wake-word training is running"
ensure_label "$LABEL_DONE" "2da44e" "Wake word was generated and added"
ensure_label "$LABEL_FAILED" "d73a4a" "Wake-word training failed or needs attention"

if [[ -n "$REQUEST_ERROR" ]]; then
  mark_failed "$REQUEST_ERROR"
  exit 0
fi

prepare_external_storage

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

if git -C "$trainer_dir" remote get-url origin >/dev/null 2>&1; then
  log "Refreshing the external macOS trainer checkout"
  git -C "$trainer_dir" fetch --quiet origin main
  git -C "$trainer_dir" merge --ff-only FETCH_HEAD
fi

# The event payload may be hours old after runner downtime. Re-read the issue
# immediately before expensive work so closed requests and edited phrases do
# not consume the training runner.
refresh_request_from_github
if [[ "$SHOULD_TRAIN" != "1" ]]; then
  log "Issue #$ISSUE_NUMBER was closed or changed before training. Skipping it."
  clear_processing_label
  exit 0
fi
if [[ -n "$REQUEST_ERROR" ]]; then
  mark_failed "$REQUEST_ERROR"
  exit 0
fi

mkdir -p "$CATALOG_DIR"
esphome_json_path="$CATALOG_DIR/$SAFE_WORD.esphome.json"
tflite_path="$CATALOG_DIR/$SAFE_WORD.tflite"
oww_onnx_path="$CATALOG_DIR/$SAFE_WORD.oww.onnx"
nww_cnn_onnx_path="$CATALOG_DIR/$SAFE_WORD.nww.cnn.onnx"
nww_gru_onnx_path="$CATALOG_DIR/$SAFE_WORD.nww.gru.onnx"
bundle_path="$CATALOG_DIR/$SAFE_WORD.wake-bundle.json"

if [[ -f "$bundle_path" && -f "$esphome_json_path" && -f "$tflite_path" && \
      -f "$oww_onnx_path" && -f "$nww_cnn_onnx_path" && -f "$nww_gru_onnx_path" ]] && \
      bundle_package_valid "$bundle_path"; then
  log "Wake word already exists: $SAFE_WORD"
  python3 scripts/generate_wake_word_manifest.py
  raw_base="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/main"
  comment_wake_word_links \
    "Wake Word Already Exists" \
    "${raw_base}/${bundle_path}" \
    "${raw_base}/${esphome_json_path}" \
    "${raw_base}/${tflite_path}" \
    "${raw_base}/${oww_onnx_path}" \
    "${raw_base}/${nww_cnn_onnx_path}" \
    "${raw_base}/${nww_gru_onnx_path}"
  gh issue edit "$ISSUE_NUMBER" --add-label "$LABEL_DONE" --remove-label "$LABEL_PROCESSING" >/dev/null 2>&1 || true
  gh issue close "$ISSUE_NUMBER" >/dev/null 2>&1 || true
  exit 0
fi

gh issue edit "$ISSUE_NUMBER" --add-label "$LABEL_PROCESSING" --remove-label "$LABEL_FAILED" >/dev/null 2>&1 || true

output_dir="$DEFAULT_TMP_ROOT/outputs/$SAFE_WORD"
rm -rf "$output_dir"
mkdir -p "$output_dir"

# The desktop app deliberately keeps its data under ~/.taterwakewordtrainer,
# but this headless runner has a persistent external trainer checkout. Keep the
# runner's datasets and generated training data with that checkout so reruns can
# reuse them and never fill the runner account's home directory.
trainer_data_dir="${TATER_WAKE_DATA_DIR:-$trainer_dir}"
trainer_support_dir="${TATER_WAKE_SUPPORT_DIR:-$trainer_dir}"
qa_venv_dir="${MWW_CLI_QA_VENV_DIR:-$DEFAULT_TMP_ROOT/cli-reference-qa-venv}"
mkdir -p "$trainer_data_dir" "$trainer_support_dir" "$(dirname "$qa_venv_dir")"

log "Training '$RAW_PHRASE' as '$SAFE_WORD' with $trainer_dir"
log "Using external temp root: $DEFAULT_TMP_ROOT"
log "Using persistent trainer data: $trainer_data_dir"
log "Using Piper-only TTS for the resource-limited automation runner"
(
  cd "$trainer_dir"
  MWW_TTS_MODE=piper \
    MWW_ARTIFACT_SLUG="$SAFE_WORD" \
    WAKEWORD_TRAINER_SUPPORT_DIR="$trainer_support_dir" \
    WAKEWORD_TRAINER_DATA_DIR="$trainer_data_dir" \
    MWW_CLI_QA_VENV_DIR="$qa_venv_dir" \
    TMPDIR="$TMPDIR" \
    TRAINED_WAKE_WORDS_DIR="$output_dir" \
    ./train_microwakeword_macos.sh "$RAW_PHRASE"
)

for artifact in \
  "$output_dir/$SAFE_WORD.wake-bundle.json" \
  "$output_dir/$SAFE_WORD.esphome.json" \
  "$output_dir/$SAFE_WORD.tflite"; do
  if [[ ! -f "$artifact" ]]; then
    echo "Trainer did not produce the required artifact: $artifact"
    exit 1
  fi
done

python3 - <<'PY' "$output_dir/$SAFE_WORD.wake-bundle.json" "$output_dir/$SAFE_WORD.esphome.json"
from __future__ import annotations

import json
import sys
from pathlib import Path

bundle_path = Path(sys.argv[1])
bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
micro = bundle.get("micro_wake_word")
if not isinstance(micro, dict):
    raise SystemExit("Tater wake bundle is missing micro_wake_word")
micro["website"] = "https://github.com/TaterTotterson/Tater-Wake-Words"
bundle_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")

esphome_path = Path(sys.argv[2])
esphome = json.loads(esphome_path.read_text(encoding="utf-8"))
esphome["website"] = "https://github.com/TaterTotterson/Tater-Wake-Words"
esphome_path.write_text(json.dumps(esphome, indent=2) + "\n", encoding="utf-8")
PY

log "Training the matched openWakeWord ONNX companion"
python3 scripts/train_openwakeword_companion.py \
  --phrase "$RAW_PHRASE" \
  --safe-word "$SAFE_WORD" \
  --trainer-dir "$trainer_dir" \
  --data-dir "$trainer_data_dir" \
  --trained-dir "$output_dir"

for artifact in \
  "$output_dir/$SAFE_WORD.oww.onnx" \
  "$output_dir/$SAFE_WORD.wake-bundle.json"; do
  if [[ ! -f "$artifact" ]]; then
    echo "Trainer did not produce the required openWakeWord bundle artifact: $artifact"
    exit 1
  fi
done

for architecture in cnn gru; do
  architecture_label="$(printf '%s' "$architecture" | tr '[:lower:]' '[:upper:]')"
  log "Training the NanoWakeWord $architecture_label model with the shared TTS, positive, and negative samples"
  python3 scripts/train_nanowakeword_companion.py \
    --phrase "$RAW_PHRASE" \
    --safe-word "$SAFE_WORD" \
    --architecture "$architecture" \
    --trainer-dir "$trainer_dir" \
    --data-dir "$trainer_data_dir" \
    --trained-dir "$output_dir"
done

for artifact in \
  "$output_dir/$SAFE_WORD.nww.cnn.onnx" \
  "$output_dir/$SAFE_WORD.nww.gru.onnx" \
  "$output_dir/$SAFE_WORD.wake-bundle.json"; do
  if [[ ! -f "$artifact" ]]; then
    echo "Trainer did not produce the required NanoWakeWord bundle artifact: $artifact"
    exit 1
  fi
done

cp "$output_dir/$SAFE_WORD.esphome.json" "$esphome_json_path"
cp "$output_dir/$SAFE_WORD.tflite" "$tflite_path"
cp "$output_dir/$SAFE_WORD.oww.onnx" "$oww_onnx_path"
cp "$output_dir/$SAFE_WORD.nww.cnn.onnx" "$nww_cnn_onnx_path"
cp "$output_dir/$SAFE_WORD.nww.gru.onnx" "$nww_gru_onnx_path"
cp "$output_dir/$SAFE_WORD.wake-bundle.json" "$bundle_path"

if ! bundle_package_valid "$bundle_path"; then
  echo "Published wake bundle failed engine, filename, size, or SHA-256 validation."
  exit 1
fi

python3 scripts/generate_wake_word_manifest.py

git add \
  "$esphome_json_path" \
  "$tflite_path" \
  "$oww_onnx_path" \
  "$nww_cnn_onnx_path" \
  "$nww_gru_onnx_path" \
  "$bundle_path" \
  wake_word_manifest.json
if git diff --cached --quiet; then
  log "No catalog changes to commit."
else
  git commit -m "Add wake word: $SAFE_WORD"
  git push
fi

raw_base="https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/main"
comment_wake_word_links \
  "Wake Word Added" \
  "${raw_base}/${bundle_path}" \
  "${raw_base}/${esphome_json_path}" \
  "${raw_base}/${tflite_path}" \
  "${raw_base}/${oww_onnx_path}" \
  "${raw_base}/${nww_cnn_onnx_path}" \
  "${raw_base}/${nww_gru_onnx_path}"
gh issue edit "$ISSUE_NUMBER" --add-label "$LABEL_DONE" --remove-label "$LABEL_PROCESSING" >/dev/null 2>&1 || true
gh issue close "$ISSUE_NUMBER" >/dev/null 2>&1 || true
log "Completed issue #$ISSUE_NUMBER for $SAFE_WORD"
