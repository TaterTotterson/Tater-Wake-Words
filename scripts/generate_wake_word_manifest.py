#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "wake_word_manifest.json"
REPO_OWNER = os.environ.get("WAKE_WORD_REPO_OWNER", "TaterTotterson")
REPO_NAME = os.environ.get("WAKE_WORD_REPO_NAME", "Tater-Wake-Words")
REPO_REF = os.environ.get("WAKE_WORD_REPO_REF", "main")


def source_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"(\d+)$", path.name)
    return (int(match.group(1)) if match else 9999, path.name.lower())


def source_dirs() -> list[Path]:
    return sorted(
        [path for path in REPO_ROOT.glob("microWakeWordsV*") if path.is_dir()],
        key=source_sort_key,
    )


def slug_to_label(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        return "Wake Word"
    parts = [part for part in re.split(r"[_\-\s]+", token) if part]
    return " ".join(part.capitalize() for part in parts) if parts else token


def raw_url(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{REPO_REF}/{rel}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def optional_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if parsed.is_integer() else parsed


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dual_model_fields(json_path: Path, model_path: Path) -> dict[str, Any]:
    slug = json_path.stem
    bundle_path = json_path.with_name(f"{slug}.wake-bundle.json")
    metadata_path = json_path.with_name(f"{slug}.oww.json")
    onnx_path = json_path.with_name(f"{slug}.oww.onnx")
    if not all(path.is_file() for path in (bundle_path, metadata_path, onnx_path)):
        return {}

    bundle = load_json(bundle_path)
    micro = bundle.get("micro_wake_word") if isinstance(bundle.get("micro_wake_word"), dict) else {}
    oww = bundle.get("open_wake_word") if isinstance(bundle.get("open_wake_word"), dict) else {}
    artifacts = oww.get("artifacts") if isinstance(oww.get("artifacts"), dict) else {}
    onnx_artifacts = [
        row
        for row in artifacts.values()
        if isinstance(row, dict) and str(row.get("file") or "").lower().endswith(".onnx")
    ]
    if (
        bundle.get("schema_version") != 1
        or bundle.get("type") != "tater_wake_word_bundle"
        or micro.get("manifest") != json_path.name
        or micro.get("model") != model_path.name
        or oww.get("metadata") != metadata_path.name
        or len(onnx_artifacts) != 1
        or onnx_artifacts[0].get("file") != onnx_path.name
    ):
        return {}

    onnx_artifact = onnx_artifacts[0]
    verified = (
        str(micro.get("manifest_sha256") or "").lower() == file_sha256(json_path)
        and str(micro.get("model_sha256") or "").lower() == file_sha256(model_path)
        and str(oww.get("metadata_sha256") or "").lower() == file_sha256(metadata_path)
        and str(onnx_artifact.get("sha256") or "").lower() == file_sha256(onnx_path)
        and optional_number(onnx_artifact.get("size_bytes")) == onnx_path.stat().st_size
    )
    if not verified:
        return {}

    fields: dict[str, Any] = {
        "dual_model": True,
        "bundle_path": bundle_path.relative_to(REPO_ROOT).as_posix(),
        "bundle_url": raw_url(bundle_path),
        "openwakeword_metadata_path": metadata_path.relative_to(REPO_ROOT).as_posix(),
        "openwakeword_metadata_url": raw_url(metadata_path),
        "openwakeword_model_path": onnx_path.relative_to(REPO_ROOT).as_posix(),
        "openwakeword_model_url": raw_url(onnx_path),
    }
    for source_key, target_key in (
        ("recommended_threshold", "openwakeword_threshold"),
        ("recommended_patience", "openwakeword_patience"),
        ("recommended_confirmation_threshold", "openwakeword_confirmation_threshold"),
        ("recommended_confirmation_patience", "openwakeword_confirmation_patience"),
    ):
        value = optional_number(oww.get(source_key))
        if value is not None:
            fields[target_key] = value
    return fields


def build_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for source_dir in source_dirs():
        source_key = source_dir.name
        source_label = source_key
        for json_path in sorted(source_dir.glob("*.json")):
            if json_path.name.endswith(".esphome.json"):
                continue
            model_path = json_path.with_suffix(".tflite")
            if not model_path.is_file():
                continue
            payload = load_json(json_path)
            slug = json_path.stem
            wake_word = str(payload.get("wake_word") or slug).strip() or slug
            micro = payload.get("micro") if isinstance(payload.get("micro"), dict) else {}
            native = payload.get("tater_native") if isinstance(payload.get("tater_native"), dict) else {}
            calibration = payload.get("calibration") if isinstance(payload.get("calibration"), dict) else {}

            entry: dict[str, Any] = {
                "id": f"{source_key}:{slug}",
                "source": source_key,
                "source_label": source_label,
                "slug": slug,
                "name": wake_word,
                "label": str(
                    payload.get("display_name")
                    or payload.get("title")
                    or payload.get("label")
                    or slug_to_label(wake_word)
                ),
                "path": json_path.relative_to(REPO_ROOT).as_posix(),
                "model_path": model_path.relative_to(REPO_ROOT).as_posix(),
                "url": raw_url(json_path),
                "download_url": raw_url(json_path),
                "model_url": raw_url(model_path),
            }
            esphome_path = json_path.with_name(f"{json_path.stem}.esphome.json")
            if esphome_path.is_file():
                entry["esphome_path"] = esphome_path.relative_to(
                    REPO_ROOT
                ).as_posix()
                entry["esphome_url"] = raw_url(esphome_path)

            entry.update(dual_model_fields(json_path, model_path))

            for key in ("author", "model_format", "quantization", "sample_rate", "version"):
                if payload.get(key) not in (None, ""):
                    entry[key] = payload.get(key)

            languages = payload.get("trained_languages")
            if isinstance(languages, list) and languages:
                entry["trained_languages"] = [str(item) for item in languages if str(item).strip()]

            threshold = optional_number(native.get("wake_threshold"))
            if threshold is None:
                threshold = optional_number(micro.get("probability_cutoff"))
            window = optional_number(native.get("wake_sliding_window"))
            if window is None:
                window = optional_number(micro.get("sliding_window_size"))
            close_miss = optional_number(native.get("close_miss_threshold"))

            if threshold is not None:
                entry["wake_threshold"] = threshold
            if window is not None:
                entry["wake_sliding_window"] = window
            if close_miss is not None:
                entry["close_miss_threshold"] = close_miss
            if calibration.get("recall") is not None:
                entry["calibration_recall"] = calibration.get("recall")
            if calibration.get("false_accepts_per_hour") is not None:
                entry["calibration_false_accepts_per_hour"] = calibration.get("false_accepts_per_hour")
            if micro.get("minimum_esphome_version"):
                entry["minimum_esphome_version"] = str(micro.get("minimum_esphome_version"))

            entries.append(entry)

    entries.sort(
        key=lambda item: (
            source_sort_key(REPO_ROOT / str(item.get("source") or "")),
            str(item.get("label") or "").lower(),
            str(item.get("slug") or "").lower(),
        )
    )
    return entries


def build_manifest() -> dict[str, Any]:
    entries = build_entries()
    paired_entries = [entry for entry in entries if entry.get("dual_model") and entry.get("bundle_url")]
    sources = []
    for source_dir in source_dirs():
        count = sum(1 for entry in entries if entry.get("source") == source_dir.name)
        if count:
            sources.append({"key": source_dir.name, "label": source_dir.name, "count": count})
    return {
        "schema_version": 2,
        "repository": f"{REPO_OWNER}/{REPO_NAME}",
        "ref": REPO_REF,
        "catalogs": {
            "micro_wake_word": {
                "label": "microWakeWord",
                "count": len(entries),
                "url_field": "url",
            },
            "open_wake_word": {
                "label": "openWakeWord",
                "count": len(paired_entries),
                "url_field": "bundle_url",
                "requires": ["dual_model"],
            },
            "dual_wake_word": {
                "label": "Dual Wake Word",
                "count": len(paired_entries),
                "url_field": "bundle_url",
                "requires": ["dual_model"],
            },
        },
        "sources": sources,
        "count": len(entries),
        "entries": entries,
    }


def main() -> None:
    manifest = build_manifest()
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} with {manifest.get('count', 0)} entries.")


if __name__ == "__main__":
    main()
