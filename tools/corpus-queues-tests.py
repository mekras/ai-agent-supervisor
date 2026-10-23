#!/usr/bin/env python3
"""Проверить очереди на непустом корпусе без сети и распознавания речи."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import yaml

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("corpus_queues", Path(__file__).with_name("corpus-queues.py"))
queues = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queues)


class QueuesTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="очереди корпуса ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(queues, "ROOT", self.root).start()
        binaries = self.root / "bin"
        binaries.mkdir()
        ffmpeg = binaries / "ffmpeg"
        ffmpeg.write_text(f"#!{sys.executable}\nraise SystemExit(0)\n")
        ffmpeg.chmod(0o755)
        patch.dict(os.environ, {"PATH": str(binaries) + os.pathsep + os.environ["PATH"]}).start()
        self.corpus = self.root / "knowledge"
        self.source = self.corpus / "data/example"
        self.item = self.source / "pages/one"
        self.item.mkdir(parents=True)
        self.put(self.corpus / "corpus.yml", {"contract_version": 1})
        self.put(self.source / "source.yml", {"id": "TEST", "copy_policy": "local_only"})
        self.put(self.source / "items.yml", {"items": [{"id": "TEST--one", "source_id": "TEST", "path": "pages/one",
                                                       "locator": "https://example.org/one", "workflow_stage": "indexed"}]})
        self.put(self.item / "item.yml", {"id": "TEST--one", "source_id": "TEST", "workflow_stage": "needs_fetch"})

    def put(self, path, value):
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def card(self, **values):
        path = self.item / "item.yml"
        self.put(path, {**queues.load(path), **values})

    def run_queue(self, operation, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            code = queues.main([operation, "knowledge", *arguments])
        return code, json.loads(output.getvalue())

    def statements(self, excerpt="Сохранённый фрагмент.", processing=None):
        self.card(workflow_stage="normalized")
        (self.item / "normalized.local.md").write_text("Сохранённый\nфрагмент. Ещё одна фраза.", encoding="utf-8")
        value = {"statement_contract_version": 2, "statements": [{"id": "TEST-001", "source_id": "TEST", "item_id": "TEST--one",
                 "excerpt": excerpt, "artifact": "normalized.local.md", "processing_status": processing or {
                     "extraction": "complete", "traceability": "pending", "semantic_review": "pending"}}]}
        self.put(self.item / "statements.yml", value)

    def media(self):
        self.card(workflow_stage="needs_transcript", input_media="recording.local.wav")
        (self.item / "recording.local.wav").write_bytes(b"synthetic media for the command contract")

    def test_fetch_records_bytes_hash_and_stage_then_repeats_without_network(self):
        with patch.object(queues, "download", return_value=(b"<p>Original</p>", "text/html")) as download:
            code, output = self.run_queue("fetch")
            self.assertEqual(code, 0)
            self.assertEqual(output["changed"], 1)
            receipt = queues.load(self.item / "acquisition.local.yml")
            blob = self.item / receipt["artifact"]
            self.assertEqual(blob.read_bytes(), b"<p>Original</p>")
            self.assertEqual(receipt["sha256"], queues.file_digest(blob))
            self.assertEqual(queues.load(self.item / "item.yml")["workflow_stage"], "fetched")
            first = (self.item / "item.yml").read_bytes()
            self.assertEqual(self.run_queue("fetch")[1]["changed"], 0)
            self.assertEqual((self.item / "item.yml").read_bytes(), first)
            self.card(workflow_stage="needs_fetch")
            self.assertEqual(self.run_queue("fetch")[0], 0)
            self.assertEqual(download.call_count, 1)

    def test_fetch_resumes_after_card_write_interruption(self):
        before = (self.item / "item.yml").read_bytes()
        with patch.object(queues, "download", return_value=(b"audio", "audio/wav")) as download:
            with patch.object(queues, "update_card", side_effect=OSError("interrupted")):
                self.assertEqual(self.run_queue("fetch")[0], 2)
            self.assertEqual((self.item / "item.yml").read_bytes(), before)
            self.assertEqual(self.run_queue("fetch")[0], 0)
            self.assertEqual(download.call_count, 1)
        self.assertEqual(queues.load(self.item / "item.yml")["workflow_stage"], "needs_transcript")

    def test_fetch_failure_leaves_card_and_no_receipt(self):
        before = (self.item / "item.yml").read_bytes()
        with patch.object(queues, "download", side_effect=queues.QueueError("network failed")):
            self.assertEqual(self.run_queue("fetch")[0], 2)
        self.assertEqual((self.item / "item.yml").read_bytes(), before)
        self.assertFalse((self.item / "acquisition.local.yml").exists())

    def test_fetch_detects_changed_snapshot_without_overwriting_it(self):
        with patch.object(queues, "download", return_value=(b"original", "text/plain")):
            self.run_queue("fetch")
        receipt = queues.load(self.item / "acquisition.local.yml")
        blob = self.item / receipt["artifact"]
        blob.write_bytes(b"another writer")
        self.card(workflow_stage="needs_fetch")
        with patch.object(queues, "download") as download:
            self.assertEqual(self.run_queue("fetch")[0], 2)
            download.assert_not_called()
        self.assertEqual(blob.read_bytes(), b"another writer")

    def test_fetch_does_not_replace_receipt_created_during_download(self):
        receipt = self.item / "acquisition.local.yml"

        def download(*args):
            receipt.write_bytes(b"another writer")
            return b"original", "text/plain"

        with patch.object(queues, "download", side_effect=download):
            self.assertEqual(self.run_queue("fetch")[0], 2)
        self.assertEqual(receipt.read_bytes(), b"another writer")
        self.assertEqual(queues.load(self.item / "item.yml")["workflow_stage"], "needs_fetch")

    def test_indexed_unselected_and_rejected_units_are_not_fetched(self):
        with patch.object(queues, "download") as download:
            self.card(workflow_stage="indexed")
            self.assertEqual(self.run_queue("fetch")[1]["changed"], 0)
            self.card(workflow_stage="needs_fetch", selection="rejected")
            self.assertEqual(self.run_queue("fetch")[1]["changed"], 0)
            download.assert_not_called()

    def test_selected_indexed_unit_can_be_fetched_without_existing_card(self):
        (self.item / "item.yml").unlink()
        path = self.source / "items.yml"
        value = queues.load(path)
        value["items"][0]["processing_scope"] = "selected_fragments"
        self.put(path, value)
        with patch.object(queues, "download", return_value=(b"source", "text/plain")):
            self.assertEqual(self.run_queue("fetch")[0], 0)
        self.assertEqual(queues.load(self.item / "item.yml")["workflow_stage"], "fetched")

    def test_fragment_only_copy_policy_does_not_authorize_full_snapshot(self):
        path = self.source / "source.yml"
        self.put(path, {**queues.load(path), "copy_policy": "selected_fragments"})
        with patch.object(queues, "download") as download:
            self.assertEqual(self.run_queue("fetch")[0], 2)
            download.assert_not_called()

    def test_transcribe_executes_fake_engine_and_preserves_raw_text(self):
        self.media()
        model = self.root / "model.pt"
        model.write_bytes(b"fixture model, no inference")
        engine = self.root / "fake-whisper"
        engine.write_text(f'''#!{sys.executable}
import json, os, pathlib, sys
arguments = sys.argv[1:]
media = pathlib.Path(arguments[0])
output = pathlib.Path(arguments[arguments.index('--output_dir')+1])
(output / (media.stem+'.txt')).write_text('Сырой текст.\\n', encoding='utf-8')
(media.parent / 'engine.local.json').write_text(json.dumps({{'args': arguments, 'threads': os.environ['OMP_NUM_THREADS']}}))
''', encoding="utf-8")
        engine.chmod(0o755)
        with patch.object(queues, "resources"):
            code, _ = self.run_queue("transcribe", "--whisper-program", str(engine), "--whisper-model", str(model))
        self.assertEqual(code, 0)
        transcript = self.item / "transcript.local.txt"
        self.assertEqual(transcript.read_text(), "Сырой текст.\n")
        receipt = queues.load(self.item / "transcription.local.yml")
        self.assertEqual(receipt["transcript_sha256"], queues.file_digest(transcript))
        self.assertEqual(receipt["input_sha256"], queues.file_digest(self.item / "recording.local.wav"))
        invocation = json.loads((self.item / "engine.local.json").read_text())
        self.assertEqual(invocation["threads"], "2")
        self.assertIn(str(model), invocation["args"])
        self.assertEqual(queues.load(self.item / "item.yml")["workflow_stage"], "raw_transcribed")
        self.card(workflow_stage="needs_transcript")
        self.assertEqual(self.run_queue("transcribe", "--whisper-program", "does-not-exist")[0], 0)
        self.assertEqual(transcript.read_text(), "Сырой текст.\n")
        self.assertFalse(list(self.item.glob("whisper.tmp.*")))

    def test_missing_model_or_low_resources_leave_transcription_pending(self):
        self.media()
        before = (self.item / "item.yml").read_bytes()
        self.assertEqual(self.run_queue("transcribe", "--whisper-model", str(self.root / "absent.pt"))[0], 2)
        self.assertEqual((self.item / "item.yml").read_bytes(), before)
        self.assertFalse((self.item / "transcript.local.txt").exists())
        with patch.object(queues.shutil, "disk_usage") as disk:
            disk.return_value.free = 0
            with self.assertRaises(queues.QueueError):
                queues.resources(self.item, self.item / "recording.local.wav", self.root / "absent.pt")

    def test_existing_unattributed_transcript_is_never_replaced(self):
        self.media()
        transcript = self.item / "transcript.local.txt"
        transcript.write_text("Чужой текст.", encoding="utf-8")
        self.assertEqual(self.run_queue("transcribe")[0], 2)
        self.assertEqual(transcript.read_text(), "Чужой текст.")

    def test_traceability_marks_only_links_and_saves_artifact_hash(self):
        self.statements()
        self.assertEqual(self.run_queue("traceability")[1]["changed"], 1)
        document = queues.load(self.item / "statements.yml")
        flags = document["statements"][0]["processing_status"]
        self.assertEqual(flags["traceability"], "passed")
        self.assertEqual(flags["semantic_review"], "pending")
        receipt = queues.load(self.item / "traceability.local.yml")
        self.assertEqual(receipt["statements"][0]["sha256"], queues.file_digest(self.item / "normalized.local.md"))
        before = (self.item / "statements.yml").read_bytes()
        self.assertEqual(self.run_queue("traceability")[1]["changed"], 0)
        self.assertEqual((self.item / "statements.yml").read_bytes(), before)

    def test_invalid_quote_does_not_pass_traceability(self):
        self.statements(excerpt="Этого текста нет.")
        before = (self.item / "statements.yml").read_bytes()
        self.assertEqual(self.run_queue("traceability")[0], 2)
        self.assertEqual((self.item / "statements.yml").read_bytes(), before)
        self.assertFalse((self.item / "traceability.local.yml").exists())

    def test_traceability_never_completes_unfinished_extraction(self):
        self.statements(processing={"extraction": "pending", "traceability": "pending"})
        self.assertEqual(self.run_queue("traceability")[0], 2)
        self.assertEqual(queues.load(self.item / "statements.yml")["statements"][0]["processing_status"]["extraction"], "pending")

    def test_cross_item_reference_is_rejected(self):
        self.statements()
        path = self.item / "statements.yml"
        value = queues.load(path)
        value["statements"][0]["item_id"] = "TEST--other"
        self.put(path, value)
        self.assertEqual(self.run_queue("traceability")[0], 2)

    def test_paths_urls_and_concurrent_writer_fail_without_overwriting(self):
        for raw in ("../outside", "/tmp/outside"):
            with self.assertRaises(queues.QueueError):
                queues.inside(self.item, raw)
        (self.item / "link").symlink_to(self.root)
        with self.assertRaises(queues.QueueError):
            queues.inside(self.item, "link/file")
        for url in ("file:///etc/passwd", "https://user:password@example.org", "https://example.org/?token=secret"):
            with self.assertRaises(queues.QueueError):
                queues.public_url(url)
        path = self.item / "item.yml"
        with self.assertRaises(queues.QueueError):
            queues.write(path, b"overwrite", expected=b"obsolete")
        with queues.locked(self.corpus):
            with self.assertRaises(queues.QueueError):
                with queues.locked(self.corpus):
                    pass

    def test_original_artifacts_are_ignored_by_git(self):
        (self.root / ".gitignore").write_text("*.local.*\n*.tmp.*\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        with patch.object(queues, "download", return_value=(b"private original", "text/html")):
            self.run_queue("fetch")
        for path in (self.item / "acquisition.local.yml", *self.item.glob("snapshot-*.local.*")):
            result = subprocess.run(["git", "check-ignore", "--quiet", str(path)], cwd=self.root)
            self.assertEqual(result.returncode, 0)

    def test_http_download_limits_empty_response_and_network_errors(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/error":
                    self.send_error(500)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                if self.path != "/empty":
                    self.wfile.write(b"actual response")

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            self.assertEqual(queues.download(url, 100), (b"actual response", "text/plain"))
            for address, maximum in ((url, 2), (url + "/empty", 100), (url + "/error", 100)):
                with self.assertRaises(queues.QueueError):
                    queues.download(address, maximum)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_admission_failure_prevents_all_processing(self):
        self.put(self.corpus / "corpus.yml", {"source_admission": {"version": 1}})
        before = (self.item / "item.yml").read_bytes()
        with patch.object(queues, "download") as download:
            with self.assertRaises(queues.QueueError):
                self.run_queue("fetch")
            download.assert_not_called()
        self.assertEqual((self.item / "item.yml").read_bytes(), before)

    def test_failed_attempt_is_included_in_batch_limit(self):
        path = self.source / "items.yml"
        index = queues.load(path)
        index["items"].append({"id": "TEST--two", "source_id": "TEST", "path": "pages/two", "workflow_stage": "needs_fetch",
                               "locator": "https://example.org/two"})
        self.put(path, index)
        with patch.object(queues, "download", side_effect=queues.QueueError("network failed")) as download:
            code, output = self.run_queue("fetch")
        self.assertEqual(code, 2)
        self.assertEqual(len(output["results"]), 1)
        self.assertEqual(download.call_count, 1)

    def test_second_invalid_statement_prevents_partial_pass(self):
        self.statements()
        path = self.item / "statements.yml"
        document = queues.load(path)
        document["statements"].append({**document["statements"][0], "id": "TEST-002", "excerpt": "Missing excerpt"})
        self.put(path, document)
        before = path.read_bytes()
        self.assertEqual(self.run_queue("traceability")[0], 2)
        self.assertEqual(path.read_bytes(), before)

    def test_duplicate_statement_identifiers_stop_processing(self):
        self.statements()
        path = self.item / "statements.yml"
        document = queues.load(path)
        document["statements"].append(document["statements"][0])
        self.put(path, document)
        with self.assertRaises(queues.QueueError):
            self.run_queue("traceability")

    def test_engine_error_preserves_media_and_pending_stage(self):
        self.media()
        before = (self.item / "item.yml").read_bytes()
        model = self.root / "model.pt"
        model.write_bytes(b"fixture")
        engine = self.root / "failing-whisper"
        engine.write_text(f"#!{sys.executable}\nraise SystemExit(1)\n")
        engine.chmod(0o755)
        with patch.object(queues, "resources"):
            self.assertEqual(self.run_queue("transcribe", "--whisper-program", str(engine), "--whisper-model", str(model))[0], 2)
            engine.write_text(f"#!{sys.executable}\nraise SystemExit(0)\n")
            self.assertEqual(self.run_queue("transcribe", "--whisper-program", str(engine), "--whisper-model", str(model))[0], 2)
        self.assertEqual((self.item / "item.yml").read_bytes(), before)
        self.assertTrue((self.item / "recording.local.wav").exists())
        self.assertFalse((self.item / "transcript.local.txt").exists())
        self.assertFalse(list(self.item.glob("whisper.tmp.*")))

    def test_controller_runs_nonempty_fetch_and_rebuilds_queue(self):
        class Handler(BaseHTTPRequestHandler):
            calls = 0

            def log_message(self, *args):
                pass

            def do_GET(self):
                Handler.calls += 1
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Source body from a local HTTP fixture.")

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.card(locator=f"http://127.0.0.1:{server.server_port}/source")
            self.put(self.corpus / "corpus.yml", {"contract_version": 1, "tracked_data": {"root": "data"}})
            self.put(self.corpus / "catalog.yml", {"sources": [{"id": "TEST", "title": "Fixture", "path": "data/example"}]})
            (self.root / ".gitignore").write_text("*.local.*\n*.tmp.*\n")
            subprocess.run(["git", "init", "-q", str(self.root)], check=True)
            tools = self.root / "tools"
            tools.mkdir()
            shutil.copyfile(Path(__file__).with_name("corpus-queues.py"), tools / "corpus-queues.py")
            self.put(self.corpus / "operations.yml", {"operations_version": 1, "stages": {"fetch": {"commands": [{
                "id": "fixture-fetch", "argv": [sys.executable, "-B", "tools/corpus-queues.py", "fetch", "knowledge"],
                "working_directory": ".", "write_paths": ["knowledge"], "required": True}]}}})
            controller = Path(__file__).resolve().parent.parent / ".agents/skills/kc-pipeline/scripts/run-corpus-operations.py"
            command = [sys.executable, "-B", str(controller), "knowledge", "--operations", "knowledge/operations.yml", "--run-commands", "--stage", "fetch"]
            for _ in range(2):
                result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, encoding="utf-8",
                                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("- fetch: 0", result.stdout)
                self.assertIn("- normalize: 1", result.stdout)
            self.assertEqual(Handler.calls, 1)
            self.assertEqual(queues.load(self.item / "item.yml")["workflow_stage"], "fetched")
            receipt = queues.load(self.item / "acquisition.local.yml")
            self.assertEqual((self.item / receipt["artifact"]).read_bytes(), b"Source body from a local HTTP fixture.")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_project_operations_are_accepted_by_installed_controller(self):
        project = Path(__file__).resolve().parent.parent
        controller = project / ".agents/skills/kc-pipeline/scripts/run-corpus-operations.py"
        result = subprocess.run(
            [sys.executable, "-B", str(controller), "knowledge", "--operations", "knowledge/operations.yml"],
            cwd=project, capture_output=True, text=True, encoding="utf-8", timeout=30,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_project_source_routes_have_scoped_index_executor(self):
        project = Path(__file__).resolve().parent.parent
        path = project / ".agents/skills/kc-pipeline/scripts/run-corpus-operations.py"
        spec = importlib.util.spec_from_file_location("setup_corpus_controller", path)
        controller = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = controller
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(controller)
        sources = controller.load_sources(project / "knowledge")
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(source=source.source_id):
                self.assertEqual(source.adapter, "agent")
                self.assertTrue(controller.valid_agent_route(project, source))
                route = source.agent_route
                self.assertFalse(controller.valid_agent_route(project, controller.CorpusSource(
                    source.source_id, source.source_dir, {**source.card, "agent_route": {**route, "write_scope": ["."]}}
                )))


if __name__ == "__main__":
    unittest.main()
