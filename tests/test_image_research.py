"""Optional image research contracts; archive examples here are synthetic fixtures."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import image_research as ir


class ImageResearchContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ivanvideo-visual-")
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        (self.root / "project.json").write_text('{"width":960,"height":540,"fps":30}')
        (self.root / "storyboard.json").write_text('{"shots":[]}')
        self.repo = Path(self.temp.name) / "archive"
        self.engine = {"repository": str(self.repo), "python": sys.executable, "commit": "fixture", "dataset_version": "fixture-only"}
        self.available = {"available": True, "engine": self.engine, "archive_status": {"ready": True, "active_taxonomy_version": ir.TAXONOMY}, "reason": None}
        self.intent = "literal user intent"
        self.source_prompt = "Synthetic fixture only\r\n原文保持 Unicode 与换行。"
        self.record = {"tweet_id": "fixture-1", "author": "Synthetic Fixture", "source_url": "https://example.invalid/fixture-1",
                       "source_prompt": self.source_prompt, "match_kind": "exact", "missing_constraints": [],
                       "match_reasons": [{"type": "fixture-only"}], "images": {"representative": {
                           "url": "https://example.invalid/fixture.png", "local_path": "images/fixture-1/1.png"}}}
        self.payload = {"schema_version": "oip-retrieval-v1", "taxonomy_version": ir.TAXONOMY,
                        "query": self.intent, "parsed_intent": {"query": self.intent}, "results": [self.record], "related_results": []}

    def tearDown(self):
        self.temp.cleanup()

    def capture(self, payload=None, out="references/image-research.json"):
        with patch.object(ir, "archive_status", return_value=self.available), patch.object(ir, "call_engine", return_value=payload or self.payload):
            return ir.search(self.root, self.intent, out=out)

    def update(self, value):
        (self.root / "references/image-research.json").write_bytes(ir.encoded(value))

    def test_absent_optional_files_leave_old_project_unchanged(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(ir.check(self.root)["research"], "not_configured")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_missing_engine_records_unavailable_without_install_or_query(self):
        with patch.object(ir, "call_engine") as engine:
            result = ir.search(self.root, self.intent, repo=self.repo)
            engine.assert_not_called()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(ir.check(self.root)["research"], "unavailable")

    def test_wrong_taxonomy_does_not_proceed_to_search(self):
        (self.repo / "skills/img-gen-prompts/scripts").mkdir(parents=True)
        (self.repo / "skills/img-gen-prompts/scripts/oip.py").write_text("")
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts/prompt_library.py").write_text("")
        version = type("Version", (), {"stdout": "3 13"})()
        with patch.object(ir.subprocess, "run", return_value=version), patch.object(ir, "call_engine", return_value={"ready": True, "active_taxonomy_version": "legacy"}) as engine:
            result = ir.archive_status(self.repo)
        self.assertFalse(result["available"])
        self.assertEqual(engine.call_count, 1)

    def test_original_prompt_bytes_and_pending_missing_image(self):
        result = self.capture()
        record = result["records"][0]
        self.assertEqual(record["source_prompt"].encode(), self.source_prompt.encode())
        self.assertFalse(record["image"]["exists_at_search"])
        self.assertFalse(record["selected"])
        self.assertEqual(ir.check(self.root)["selected"], 0)

    def test_empty_results_remain_empty(self):
        payload = dict(self.payload, results=[])
        self.assertEqual(self.capture(payload)["status"], "no_matches")
        self.assertEqual(ir.check(self.root)["research"], "no_matches")

    def test_related_preserves_missing_constraint(self):
        item = dict(self.record, match_kind="related", missing_constraints=["lighting:soft"])
        result = self.capture(dict(self.payload, results=[], related_results=[item]))
        self.assertEqual(result["records"][0]["match_kind"], "related")
        self.assertEqual(result["records"][0]["missing_constraints"], ["lighting:soft"])
        self.assertTrue(ir.check(self.root)["valid"])

    def test_broken_channel_fails_closed(self):
        payload = copy.deepcopy(self.payload)
        payload["results"][0]["match_kind"] = "related"
        result = self.capture(payload)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["records"], [])

    def test_malformed_archive_records_do_not_become_recommendations(self):
        payload = copy.deepcopy(self.payload)
        payload["results"][0]["images"] = {}
        result = self.capture(payload)
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["records"])

    def test_external_image_path_is_not_reported_as_local_archive_image(self):
        payload = copy.deepcopy(self.payload)
        payload["results"][0]["images"]["representative"]["absolute_local_path"] = str(self.root / "project.json")
        result = self.capture(payload)
        self.assertIsNone(result["records"][0]["image"]["path"])
        self.assertFalse(result["records"][0]["image"]["exists_at_search"])

    def test_engine_failure_is_recorded_without_retry(self):
        with patch.object(ir, "archive_status", return_value=self.available), patch.object(ir, "call_engine", side_effect=ValueError("synthetic engine failure")) as engine:
            result = ir.search(self.root, self.intent)
        self.assertEqual(engine.call_count, 1)
        self.assertEqual(result["status"], "unavailable")
        self.assertTrue(ir.check(self.root)["valid"])

    def test_modified_source_and_channel_are_rejected(self):
        result = self.capture()
        result["records"][0]["source_prompt"] += "edited"
        self.update(result)
        with self.assertRaisesRegex(ValueError, "source field changed"):
            ir.check(self.root)

    def test_changed_snapshot_is_rejected(self):
        result = self.capture()
        (self.root / result["source_snapshot"]).write_text("{}")
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            ir.check(self.root)

    def test_selected_reference_requires_actual_review_declaration(self):
        result = self.capture()
        result["records"][0]["selected"] = True
        self.update(result)
        with self.assertRaisesRegex(ValueError, "actual visual review"):
            ir.check(self.root)

    def test_derived_prompt_binds_existing_plan_without_schema_changes(self):
        result = self.capture()
        record = result["records"][0]
        record.update(selected=True, reuse_notes="Synthetic visual decision for unit test", prompt_kind="generation_prompt")
        record["visual_review"] = {"status": "reviewed", "method": "synthetic-test-declaration", "notes": "Not an actual archive image review"}
        result["derivations"] = [{"asset_id": "A01", "source_ids": [record["id"]], "prompt_en": "New test prompt", "prompt_zh": "新测试提示词", "rationale": "Synthetic contract test"}]
        (self.root / "references/asset-plan.json").write_bytes(ir.encoded({"assets": [{"id": "A01", "prompt": "New test prompt"}]}))
        self.update(result)
        self.assertEqual(ir.check(self.root)["derived_assets"], 1)
        result["derivations"][0]["prompt_en"] = "Different request"
        self.update(result)
        with self.assertRaisesRegex(ValueError, "existing asset plan"):
            ir.check(self.root)

    def test_unselected_reference_cannot_be_cited(self):
        result = self.capture()
        result["derivations"] = [{"asset_id": "A01", "source_ids": ["fixture-1"]}]
        self.update(result)
        with self.assertRaisesRegex(ValueError, "selected references"):
            ir.check(self.root)

    def test_existing_report_and_escaping_path_are_preserved(self):
        self.capture()
        original = (self.root / "references/image-research.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "output exists"):
            self.capture()
        with self.assertRaisesRegex(ValueError, "stay inside"):
            self.capture(out="../escape.json")
        self.assertEqual((self.root / "references/image-research.json").read_bytes(), original)

    def test_query_and_parsed_constraints_are_immutable(self):
        result = self.capture()
        result["parsed_intent"]["query"] = "changed"
        self.update(result)
        with self.assertRaisesRegex(ValueError, "parsed intent changed"):
            ir.check(self.root)

    def test_direction_contract_and_migration_check_need_no_archive(self):
        self.capture()
        spec = {name: "example" for name in ("subject", "use", "composition", "material_texture", "lighting", "palette", "mood", "aspect_ratio")}
        spec.update(style_card_id=None, invariants=["literal subject"], avoid=[])
        spec["aspect_ratio"] = "16:9"
        (self.root / "references/visual-direction.json").write_bytes(ir.encoded({"creative_spec": spec}))
        moved = Path(self.temp.name) / "moved"
        shutil.copytree(self.root, moved)
        shutil.rmtree(self.root)
        with patch.object(ir, "call_engine", side_effect=AssertionError("Historical check must be offline")):
            self.assertTrue(ir.check(moved)["valid"])
        spec["invariants"] = "invalid"
        (moved / "references/visual-direction.json").write_bytes(ir.encoded({"creative_spec": spec}))
        with self.assertRaisesRegex(ValueError, "array"):
            ir.check(moved)


if __name__ == "__main__":
    unittest.main()
