from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from stt_home.media import LocalMediaWorker, MediaError, media_policy


class MediaRuntimeTests(unittest.TestCase):
    def test_zero_cost_policy_is_fail_closed_by_default(self):
        old_worker = os.environ.pop("PARADISE_MEDIA_WORKER_CMD", None)
        old_paid = os.environ.pop("PARADISE_ALLOW_PAID_MEDIA", None)
        try:
            policy = media_policy()
            self.assertEqual(policy["default_route"], "local_self_host")
            self.assertFalse(policy["local_worker_configured"])
            self.assertFalse(policy["paid_provider_authorized"])
            self.assertTrue(policy["fail_closed"])
        finally:
            if old_worker is not None:
                os.environ["PARADISE_MEDIA_WORKER_CMD"] = old_worker
            if old_paid is not None:
                os.environ["PARADISE_ALLOW_PAID_MEDIA"] = old_paid

    def test_unconfigured_local_worker_does_not_fallback_to_paid(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.pop("PARADISE_MEDIA_WORKER_CMD", None)
            try:
                worker = LocalMediaWorker(Path(tmp))
                with self.assertRaisesRegex(MediaError, "local_media_worker_not_configured"):
                    worker.generate("image.generate", "test")
            finally:
                if old is not None:
                    os.environ["PARADISE_MEDIA_WORKER_CMD"] = old

    def test_local_worker_artifact_hash_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "result.bin"
            worker_script = root / "worker.py"
            artifact.write_bytes(b"PARADISE-TEST-ARTIFACT")
            worker_script.write_text(
                "import json,sys\n"
                "req=json.load(sys.stdin)\n"
                "print(json.dumps({'status':'COMPLETED','artifact_path':'result.bin','mime':'application/octet-stream','operation':req['operation']}))\n",
                encoding="utf-8",
            )
            old = os.environ.get("PARADISE_MEDIA_WORKER_CMD")
            os.environ["PARADISE_MEDIA_WORKER_CMD"] = f'"{sys.executable}" "{worker_script}"'
            try:
                worker = LocalMediaWorker(root)
                result = worker.generate("image.generate", "test prompt")
                self.assertEqual(result["status"], "COMPLETED")
                self.assertEqual(result["operation"], "image.generate")
                self.assertEqual(len(result["sha256"]), 64)
                self.assertTrue(result["artifact_id"].startswith("local_"))
            finally:
                if old is None:
                    os.environ.pop("PARADISE_MEDIA_WORKER_CMD", None)
                else:
                    os.environ["PARADISE_MEDIA_WORKER_CMD"] = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
