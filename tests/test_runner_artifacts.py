import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generate_wake_word_manifest as manifest


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

        self.assertIn('CATALOG_DIR="${CATALOG_DIR:-microWakeWordsV6}"', runner)
        self.assertIn("CATALOG_DIR: microWakeWordsV6", workflow)
        self.assertIn('git -C "$trainer_dir" merge --ff-only FETCH_HEAD', runner)
        self.assertIn('$SAFE_WORD.esphome.json', runner)
        self.assertIn('git add "$json_path" "$esphome_json_path" "$tflite_path"', runner)
        self.assertIn("ESPHome JSON package", runner)


if __name__ == "__main__":
    unittest.main()
