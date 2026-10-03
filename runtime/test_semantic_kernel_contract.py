import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "control"
KERNEL = CONTROL / "PARADISE_MINIMAL_SEMANTIC_KERNEL_V1.md"
CONTRACT = CONTROL / "PARADISE_IMPLEMENTATION_CONTRACT_V1.md"
CONTROL_MODEL = CONTROL / "PARADISE_CONTROL_MODEL_V1.md"
REGISTRY = CONTROL / "PARADISE_CANONICAL_REGISTRY_V1.md"


class SemanticContractAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = KERNEL.read_text(encoding="utf-8-sig")
        cls.contract = CONTRACT.read_text(encoding="utf-8-sig")
        cls.control_model = CONTROL_MODEL.read_text(encoding="utf-8-sig")
        cls.registry = REGISTRY.read_text(encoding="utf-8-sig")

    def test_exactly_19_invariants(self):
        ids = re.findall(r"^I(\d{2})\s", self.kernel, re.M)
        self.assertEqual(ids, [f"{i:02d}" for i in range(1, 20)])

    def test_exactly_7_primitives(self):
        ids = re.findall(r"^P(\d)\s", self.kernel, re.M)
        self.assertEqual(ids, [str(i) for i in range(1, 8)])

    def test_exactly_5_obligations(self):
        ids = re.findall(r"^O(\d)\s", self.kernel, re.M)
        self.assertEqual(ids, [str(i) for i in range(1, 6)])

    def test_forbidden_transition_inventory_exists(self):
        section = self.kernel.split("## 5. Forbidden transitions", 1)[1].split("## 6.", 1)[0]
        transitions = [line for line in section.splitlines() if line.startswith("- ")]
        self.assertGreaterEqual(len(transitions), 10)

    def test_all_19_are_named_in_contract(self):
        for i in range(1, 20):
            self.assertIn(f"I{i:02d}", self.contract)

    def test_boundaries_are_declared(self):
        for heading in ("## 6. Authority boundaries", "## 7. State boundaries", "## 8. Truth boundaries"):
            self.assertIn(heading, self.kernel)

    def test_governance_preserves_love_and_og_boundaries(self):
        self.assertIn("LOVE source authority: GitHub Sauthienthu89/LOVE", self.control_model)
        self.assertIn("OG is not a PARADISE project", self.control_model)
        self.assertIn("Semantic authority: F:\\OAI\\PARADISE\\control\\PARADISE_MINIMAL_SEMANTIC_KERNEL_V1.md", self.contract)

    def test_registry_has_semantic_kernel_entry(self):
        self.assertIn("PARADISE_MINIMAL_SEMANTIC_KERNEL_V1.md", self.registry)


if __name__ == "__main__":
    unittest.main(verbosity=2)