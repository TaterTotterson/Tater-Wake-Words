import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generate_wake_word_manifest as manifest
from scripts.parse_wake_word_request import parse_request, safe_slug


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

    def test_runner_requires_and_uploads_all_three_artifacts_to_v6(self) -> None:
        runner = (REPO_ROOT / "scripts" / "train_issue_wake_word.sh").read_text(
            encoding="utf-8"
        )
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "train-wake-word.yml"
        ).read_text(encoding="utf-8")
        setup = (
            REPO_ROOT / "scripts" / "setup_self_hosted_runner_macos.sh"
        ).read_text(encoding="utf-8")

        self.assertIn('CATALOG_DIR="${CATALOG_DIR:-microWakeWordsV6}"', runner)
        self.assertIn("CATALOG_DIR: microWakeWordsV6", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("tater-wake-word-${{ github.event.issue.number", workflow)
        self.assertNotIn("group: tater-wake-word-training", workflow)
        self.assertIn("timeout-minutes: 300", workflow)
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
        self.assertIn('$SAFE_WORD.esphome.json', runner)
        self.assertIn('git add "$json_path" "$esphome_json_path" "$tflite_path"', runner)
        self.assertIn("ESPHome JSON package", runner)
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


if __name__ == "__main__":
    unittest.main()
