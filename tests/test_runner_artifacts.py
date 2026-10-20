import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import generate_wake_word_manifest as manifest
from scripts.parse_wake_word_request import parse_request, safe_slug
from scripts.requeue_pending_wake_words import retry_issue_numbers


REPO_ROOT = Path(__file__).resolve().parents[1]


class RunnerArtifactTests(unittest.TestCase):
    def test_manifest_lists_esphome_companion_without_duplicate_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "microWakeWordsV6"
            catalog.mkdir()
            tater_path = catalog / "hey_tater.json"
            esphome_path = catalog / "hey_tater.esphome.json"
            model_path = catalog / "hey_tater.tflite"
            payload = {
                "type": "micro",
                "wake_word": "hey tater",
                "label": "Hey Tater",
                "model": model_path.name,
                "version": 2,
                "micro": {"probability_cutoff": 0.97},
            }
            tater_path.write_text(json.dumps(payload), encoding="utf-8")
            esphome_path.write_text(json.dumps(payload), encoding="utf-8")
            model_path.write_bytes(b"model")

            with patch.object(manifest, "REPO_ROOT", root):
                entries = manifest.build_entries()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["path"], "microWakeWordsV6/hey_tater.json")
        self.assertEqual(
            entries[0]["esphome_path"],
            "microWakeWordsV6/hey_tater.esphome.json",
        )
        self.assertTrue(entries[0]["esphome_url"].endswith("/hey_tater.esphome.json"))

    def test_manifest_exposes_verified_dual_model_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "microWakeWordsV7"
            catalog.mkdir()
            tater_path = catalog / "hey_tater.json"
            esphome_path = catalog / "hey_tater.esphome.json"
            model_path = catalog / "hey_tater.tflite"
            metadata_path = catalog / "hey_tater.oww.json"
            onnx_path = catalog / "hey_tater.oww.onnx"
            bundle_path = catalog / "hey_tater.wake-bundle.json"
            tater_path.write_text(
                json.dumps({"type": "micro", "wake_word": "hey tater", "model": model_path.name}),
                encoding="utf-8",
            )
            esphome_path.write_text("{}", encoding="utf-8")
            model_path.write_bytes(b"mww")
            metadata_path.write_text('{"type":"open_wake_word"}\n', encoding="utf-8")
            onnx_path.write_bytes(b"onnx")

            def digest(path: Path) -> str:
                return hashlib.sha256(path.read_bytes()).hexdigest()

            bundle_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "type": "tater_wake_word_bundle",
                        "wake_word": "hey tater",
                        "micro_wake_word": {
                            "manifest": tater_path.name,
                            "model": model_path.name,
                            "manifest_sha256": digest(tater_path),
                            "model_sha256": digest(model_path),
                        },
                        "open_wake_word": {
                            "metadata": metadata_path.name,
                            "metadata_sha256": digest(metadata_path),
                            "artifacts": {
                                "onnx": {
                                    "file": onnx_path.name,
                                    "sha256": digest(onnx_path),
                                    "size_bytes": onnx_path.stat().st_size,
                                }
                            },
                            "recommended_threshold": 0.96,
                            "recommended_patience": 3,
                            "recommended_confirmation_threshold": 0.88,
                            "recommended_confirmation_patience": 2,
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(manifest, "REPO_ROOT", root):
                entries = manifest.build_entries()
                catalog_manifest = manifest.build_manifest()
                onnx_path.write_bytes(b"changed")
                damaged_entries = manifest.build_entries()

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertTrue(entry["dual_model"])
        self.assertEqual(entry["source"], "microWakeWordsV7")
        self.assertEqual(entry["bundle_path"], "microWakeWordsV7/hey_tater.wake-bundle.json")
        self.assertTrue(entry["bundle_url"].endswith("/hey_tater.wake-bundle.json"))
        self.assertTrue(entry["openwakeword_model_url"].endswith("/hey_tater.oww.onnx"))
        self.assertEqual(entry["openwakeword_threshold"], 0.96)
        self.assertEqual(entry["openwakeword_confirmation_threshold"], 0.88)
        self.assertEqual(catalog_manifest["schema_version"], 3)
        self.assertEqual(catalog_manifest["catalogs"]["micro_wake_word"]["count"], 1)
        self.assertEqual(catalog_manifest["catalogs"]["open_wake_word"]["count"], 1)
        self.assertEqual(catalog_manifest["catalogs"]["dual_wake_word"]["count"], 1)
        self.assertEqual(catalog_manifest["catalogs"]["nano_wake_word"]["count"], 0)
        self.assertEqual(
            catalog_manifest["catalogs"]["open_wake_word"]["url_field"],
            "bundle_url",
        )
        self.assertNotIn("dual_model", damaged_entries[0])

    def test_empty_v7_publishes_empty_oww_and_dual_catalogs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "microWakeWordsV7"
            catalog.mkdir()

            with patch.object(manifest, "REPO_ROOT", root):
                catalog_manifest = manifest.build_manifest()

        self.assertEqual(catalog_manifest["catalogs"]["micro_wake_word"]["count"], 0)
        self.assertEqual(catalog_manifest["catalogs"]["open_wake_word"]["count"], 0)
        self.assertEqual(catalog_manifest["catalogs"]["dual_wake_word"]["count"], 0)
        self.assertEqual(catalog_manifest["catalogs"]["nano_wake_word"]["count"], 0)

    def test_manifest_exposes_verified_v8_bundle_and_nano_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "microWakeWordsV8"
            catalog.mkdir()
            bundle_path = catalog / "hey_tater.wake-bundle.json"
            esphome_path = catalog / "hey_tater.esphome.json"
            mww_path = catalog / "hey_tater.tflite"
            oww_path = catalog / "hey_tater.oww.onnx"
            cnn_path = catalog / "hey_tater.nww.cnn.onnx"
            gru_path = catalog / "hey_tater.nww.gru.onnx"
            mww_path.write_bytes(b"mww-v8")
            oww_path.write_bytes(b"oww-v8")
            cnn_path.write_bytes(b"cnn-v8")
            gru_path.write_bytes(b"gru-v8")
            esphome_path.write_text(
                json.dumps(
                    {
                        "type": "micro",
                        "wake_word": "hey tater",
                        "model": mww_path.name,
                        "micro": {"probability_cutoff": 0.99},
                    }
                ),
                encoding="utf-8",
            )

            def artifact(path: Path, *, model: bool = False) -> dict[str, object]:
                return {
                    "model" if model else "file": path.name,
                    "model_sha256" if model else "sha256": hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest(),
                    "model_size_bytes" if model else "size_bytes": path.stat().st_size,
                }

            bundle_path.write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "type": "tater_wake_word_bundle",
                        "key": "hey_tater",
                        "wake_word": "hey tater",
                        "micro_wake_word": {
                            "type": "micro",
                            "label": "Hey Tater",
                            **artifact(mww_path, model=True),
                            "micro": {"probability_cutoff": 0.99, "sliding_window_size": 5},
                        },
                        "open_wake_word": {
                            "artifacts": {"onnx": artifact(oww_path)},
                            "recommended_threshold": 0.74,
                            "recommended_patience": 3,
                        },
                        "nano_wake_word": {
                            "default_architecture": "cnn",
                            "variants": {
                                "cnn": {
                                    "architecture": "cnn",
                                    **artifact(cnn_path, model=True),
                                    "recommended_threshold": 0.99,
                                    "recommended_patience": 3,
                                },
                                "gru": {
                                    "architecture": "gru",
                                    **artifact(gru_path, model=True),
                                    "recommended_threshold": 0.98,
                                    "recommended_patience": 2,
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(manifest, "REPO_ROOT", root):
                fields = manifest.bundle_model_fields(bundle_path)
                entries = manifest.build_entries()
                catalog_manifest = manifest.build_manifest()
                cnn_path.write_bytes(b"damaged")
                damaged_entries = manifest.build_entries()

        self.assertEqual(fields["available_engines"], [
            "micro_wake_word",
            "open_wake_word",
            "nano_wake_word",
        ])
        self.assertEqual(fields["nanowakeword_architectures"], ["cnn", "gru"])
        self.assertEqual(
            fields["supported_detector_modes"],
            ["mww", "oww", "nww", "mww_oww", "mww_nww"],
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["path"], "microWakeWordsV8/hey_tater.wake-bundle.json")
        self.assertEqual(entries[0]["url"], entries[0]["bundle_url"])
        self.assertTrue(entries[0]["nanowakeword_model_urls"]["cnn"].endswith(".nww.cnn.onnx"))
        self.assertEqual(catalog_manifest["catalogs"]["nano_wake_word"]["count"], 1)
        self.assertEqual(catalog_manifest["catalogs"]["wake_word_bundle"]["count"], 1)
        self.assertEqual(damaged_entries, [])

    def test_watcher_worker_publishes_complete_bundle_package_to_v8(self) -> None:
        runner = (REPO_ROOT / "scripts" / "train_issue_wake_word.sh").read_text(
            encoding="utf-8"
        )
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "train-wake-word.yml"
        ).read_text(encoding="utf-8")
        recovery_workflow = (
            REPO_ROOT / ".github" / "workflows" / "recover-wake-word-requests.yml"
        ).read_text(encoding="utf-8")
        setup = (
            REPO_ROOT / "scripts" / "setup_self_hosted_runner_macos.sh"
        ).read_text(encoding="utf-8")
        companion = (
            REPO_ROOT / "scripts" / "train_openwakeword_companion.py"
        ).read_text(encoding="utf-8")
        nano_companion = (
            REPO_ROOT / "scripts" / "train_nanowakeword_companion.py"
        ).read_text(encoding="utf-8")

        self.assertIn('CATALOG_DIR="${CATALOG_DIR:-microWakeWordsV8}"', runner)
        # The Actions workflow is an unused manual fallback. Production uses
        # watcher.sh, which exports its own V8 destination.
        self.assertIn("CATALOG_DIR: microWakeWordsV7", workflow)
        self.assertIn('run-name: "mww #${{ inputs.issue_number', workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("types: [opened, edited, reopened]", workflow)
        self.assertIn("tater-wake-word-${{ inputs.issue_number", workflow)
        self.assertNotIn("schedule:", recovery_workflow)
        self.assertNotIn("group: tater-wake-word-training", workflow)
        self.assertIn("timeout-minutes: 360", workflow)
        self.assertIn('git -C "$trainer_dir" merge --ff-only FETCH_HEAD', runner)
        self.assertIn("MWW_TTS_MODE=piper", runner)
        self.assertNotIn("MWW_TTS_MODE=hybrid", runner)
        self.assertIn(
            'trainer_data_dir="${TATER_WAKE_DATA_DIR:-$trainer_dir}"', runner
        )
        self.assertIn(
            'WAKEWORD_TRAINER_DATA_DIR="$trainer_data_dir"', runner
        )
        self.assertIn(
            'WAKEWORD_TRAINER_SUPPORT_DIR="$trainer_support_dir"', runner
        )
        self.assertIn('MWW_ARTIFACT_SLUG="$SAFE_WORD"', runner)
        self.assertIn('./train_microwakeword_macos.sh "$RAW_PHRASE"', runner)
        self.assertIn("python3 scripts/train_openwakeword_companion.py", runner)
        self.assertIn("python3 scripts/train_nanowakeword_companion.py", runner)
        self.assertIn("for architecture in cnn gru", runner)
        self.assertLess(
            runner.index('micro["website"]'),
            runner.index("python3 scripts/train_openwakeword_companion.py"),
        )
        self.assertGreaterEqual(runner.count("refresh_request_from_github"), 3)
        self.assertIn(
            "The event payload may be hours old after runner downtime", runner
        )
        self.assertIn("clear_processing_label", runner)
        self.assertIn('$SAFE_WORD.esphome.json', runner)
        for artifact in (
            '$SAFE_WORD.oww.onnx',
            '$SAFE_WORD.nww.cnn.onnx',
            '$SAFE_WORD.nww.gru.onnx',
            '$SAFE_WORD.wake-bundle.json',
            '"$oww_onnx_path"',
            '"$nww_cnn_onnx_path"',
            '"$nww_gru_onnx_path"',
            '"$bundle_path"',
        ):
            self.assertIn(artifact, runner)
        self.assertIn("ESPHome JSON package", runner)
        self.assertIn("Tater wake bundle", runner)
        self.assertIn("bundle_package_valid", runner)
        self.assertIn("failed engine, filename, size, or SHA-256 validation", runner)
        self.assertNotIn('$SAFE_WORD.oww.json', runner)
        self.assertNotIn('$SAFE_WORD.json', runner)
        self.assertIn("prepare_openwakeword_stage", companion)
        self.assertIn("publish_openwakeword_artifacts", companion)
        self.assertIn("prepare_nanowakeword_stage", nano_companion)
        self.assertIn("publish_nanowakeword_artifacts", nano_companion)
        self.assertIn('data_dir / "generated_samples"', nano_companion)
        self.assertIn('data_dir / "personal_samples"', nano_companion)
        self.assertIn('data_dir / "negative_samples"', nano_companion)
        self.assertIn('$HOME/actions-runners/tater-wake-words', setup)
        self.assertIn('RUNNER_NAME="${RUNNER_NAME:-tater-wake-words}"', setup)

    def test_issue_event_keeps_exact_phrase_and_safe_artifact_slug(self) -> None:
        request = parse_request(
            {"issue": {"number": 93, "title": "mww: aw-la ku-kah"}}
        )

        self.assertEqual(request["SHOULD_TRAIN"], "1")
        self.assertEqual(request["ISSUE_NUMBER"], "93")
        self.assertEqual(request["RAW_PHRASE"], "aw-la ku-kah")
        self.assertEqual(request["SAFE_WORD"], "awla_kukah")

    def test_manual_retry_payload_is_supported(self) -> None:
        request = parse_request({"number": 84, "title": "mww: hey louie"})

        self.assertEqual(request["SHOULD_TRAIN"], "1")
        self.assertEqual(request["ISSUE_NUMBER"], "84")

    def test_non_ascii_phrase_gets_stable_artifact_slug(self) -> None:
        request = parse_request({"issue": {"number": 95, "title": "mww: Алиса"}})

        self.assertEqual(request["RAW_PHRASE"], "Алиса")
        self.assertEqual(request["SAFE_WORD"], "wakeword_d346fb5a")
        self.assertEqual(safe_slug("Алиса"), safe_slug("алиса"))

    def test_closed_manual_retry_exits_without_training(self) -> None:
        request = parse_request(
            {"number": 84, "title": "mww: hey louie", "state": "closed"}
        )

        self.assertEqual(request["SHOULD_TRAIN"], "0")

    def test_recovery_requeues_missing_and_stale_requests(self) -> None:
        now = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        issues = [
            {"number": 127, "title": "mww: Hey Mimiir", "labels": []},
            {"number": 128, "title": "mww: hey chat", "labels": []},
            {"number": 129, "title": "mww: Wall-E", "labels": []},
            {
                "number": 130,
                "title": "mww: retry later",
                "labels": [{"name": "mww-failed"}],
            },
            {"number": 131, "title": "not a wake word", "labels": []},
        ]
        runs = [
            {
                "displayTitle": "mww #128",
                "status": "queued",
                "createdAt": (now - timedelta(hours=2)).isoformat(),
            },
            {
                "displayTitle": "mww #129",
                "status": "queued",
                "createdAt": (now - timedelta(hours=21)).isoformat(),
            },
        ]

        self.assertEqual(retry_issue_numbers(issues, runs, now=now), [127, 129])


if __name__ == "__main__":
    unittest.main()
