from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from projects.LOVE.stt_love.state_semantics import LifecycleState, LifecycleEvent, RealityPhase
from projects.LOVE.stt_love.reality_transition import (
    AuthorityBoundary, ContractError, DecisionOutcome, EvidenceBoundary,
    OwnershipTransfer, RealityTransition, validate_transition,
)
from projects.LOVE.stt_love.store import Store, StoreError
from projects.LOVE.stt_love.og.capability_registry import CapabilityRegistry
from projects.LOVE.stt_love.durable_execution import DurableExecution
from projects.LOVE.stt_love.task_contract import TaskContract


class RealityTransitionPositiveTests(unittest.TestCase):
    def auth(self):
        return AuthorityBoundary("operator", "reality-transition", True)

    def ev(self):
        return EvidenceBoundary(("E-1",), True)

    def test_handover_receipt_acceptance(self):
        validate_transition(RealityTransition(LifecycleState.VERIFIED, LifecycleEvent.HANDOVER, LifecycleState.HANDOVER))
        validate_transition(RealityTransition(LifecycleState.HANDOVER, LifecycleEvent.RECEIPT, LifecycleState.RECEIVED))
        validate_transition(RealityTransition(LifecycleState.RECEIVED, LifecycleEvent.ACCEPTANCE, LifecycleState.ACCEPTED, DecisionOutcome.ACCEPTED))

    def test_conditional_and_rejection(self):
        validate_transition(RealityTransition(LifecycleState.RECEIVED, LifecycleEvent.CONDITIONAL_ACCEPTANCE, LifecycleState.CONDITIONAL_ACCEPTANCE, DecisionOutcome.CONDITIONALLY_ACCEPTED))
        validate_transition(RealityTransition(LifecycleState.RECEIVED, LifecycleEvent.REJECTION, LifecycleState.REJECTED, DecisionOutcome.REJECTED))

    def test_reality_path(self):
        for current, event, target in [
            (LifecycleState.ACCEPTED, LifecycleEvent.TRIAL, LifecycleState.TRIAL),
            (LifecycleState.TRIAL, LifecycleEvent.REALITY_VALIDATION, LifecycleState.REALITY_VALIDATED),
            (LifecycleState.REALITY_VALIDATED, LifecycleEvent.OPERATIONALIZATION, LifecycleState.OPERATIONALIZED),
            (LifecycleState.OPERATIONALIZED, LifecycleEvent.PRODUCTION, LifecycleState.PRODUCTION),
        ]:
            validate_transition(RealityTransition(current, event, target, evidence=self.ev(), authority=self.auth()))

    def test_closure(self):
        validate_transition(RealityTransition(LifecycleState.PRODUCTION, LifecycleEvent.CLOSURE, LifecycleState.CLOSED, evidence=self.ev(), authority=self.auth()))

    def test_ownership_transfer_is_separate(self):
        transfer = OwnershipTransfer("owner-a", "owner-b", "deployment", "acceptance-effective", "AUTH-1", ("E-1",))
        validate_transition(RealityTransition(LifecycleState.ACCEPTED, LifecycleEvent.OWNERSHIP_TRANSFER, None, ownership=transfer))

    def test_reality_phase_events(self):
        for phase in RealityPhase:
            validate_transition(RealityTransition(LifecycleState.PRODUCTION, LifecycleEvent(phase.value), None, phase=phase))


class RealityTransitionNegativeTests(unittest.TestCase):
    def assertBlocked(self, transition):
        with self.assertRaises(ContractError):
            validate_transition(transition)

    def test_handover_does_not_imply_acceptance(self):
        self.assertBlocked(RealityTransition(LifecycleState.VERIFIED, LifecycleEvent.ACCEPTANCE, LifecycleState.ACCEPTED, DecisionOutcome.ACCEPTED))

    def test_receipt_does_not_imply_acceptance(self):
        self.assertBlocked(RealityTransition(LifecycleState.HANDOVER, LifecycleEvent.ACCEPTANCE, LifecycleState.ACCEPTED, DecisionOutcome.ACCEPTED))

    def test_test_success_does_not_imply_reality_validation(self):
        self.assertBlocked(RealityTransition(LifecycleState.TESTED, LifecycleEvent.REALITY_VALIDATION, LifecycleState.REALITY_VALIDATED))

    def test_production_requires_evidence_authority(self):
        self.assertBlocked(RealityTransition(LifecycleState.OPERATIONALIZED, LifecycleEvent.PRODUCTION, LifecycleState.PRODUCTION))

    def test_ownership_transfer_not_state_transition(self):
        transfer = OwnershipTransfer("a", "b", "x", "condition", "AUTH", ())
        self.assertBlocked(RealityTransition(LifecycleState.ACCEPTED, LifecycleEvent.OWNERSHIP_TRANSFER, LifecycleState.TRIAL, ownership=transfer))

    def test_conditional_not_unconditional(self):
        self.assertBlocked(RealityTransition(LifecycleState.RECEIVED, LifecycleEvent.ACCEPTANCE, LifecycleState.ACCEPTED, DecisionOutcome.CONDITIONALLY_ACCEPTED))

    def test_closure_requires_production(self):
        self.assertBlocked(RealityTransition(LifecycleState.BASELINE if False else LifecycleState.OPERATIONALIZED, LifecycleEvent.CLOSURE, LifecycleState.CLOSED, evidence=EvidenceBoundary(("E",), True), authority=AuthorityBoundary("a", "s", True)))


class CapabilityRegistryTests(unittest.TestCase):
    def test_registry_loads_and_validates(self):
        registry = CapabilityRegistry()
        self.assertEqual(registry.status, "CANONICAL")
        self.assertTrue(registry.owner)
        self.assertEqual(registry.validate(), [])
        self.assertEqual(registry.capability_for("/research").provider, "research")

    def test_unknown_command_rejected(self):
        registry = CapabilityRegistry()
        with self.assertRaises(KeyError):
            registry.capability_for("/unknown")


class StoreTests(unittest.TestCase):
    def test_task_round_trip_and_upsert(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            task = {"id": "T1", "state": "QUEUED", "revision": 1}
            store.upsert_task(task)
            self.assertEqual(store.task_by_id("T1")["state"], "QUEUED")
            task["state"] = "RUNNING"
            task["revision"] = 2
            store.upsert_task(task)
            self.assertEqual(store.task_by_id("T1")["revision"], 2)

    def test_durable_execution_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            execution = DurableExecution(store)
            submission = TaskContract("demo").submit(submission_id="T1", idempotency_key="K1")
            task, created = execution.enqueue_submission(submission)
            self.assertTrue(created is False)
            self.assertEqual(store.task_by_id("T1")["state"], "QUEUED")
            claimed = execution.claim("T1")
            self.assertIsNotNone(claimed)
            self.assertEqual(store.task_by_id("T1")["state"], "RUNNING")

    def test_malformed_store_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "tasks.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(StoreError):
                Store(root).tasks()


if __name__ == "__main__":
    unittest.main(verbosity=2)

class RegressionTests(unittest.TestCase):
    def test_task_contract_remains_intent_only(self):
        task = TaskContract("goal", {"x": 1}).validate()
        self.assertEqual(task.goal, "goal")
        self.assertNotIn("state", task.__dict__)

    def test_command_router_registry_integration(self):
        from projects.LOVE.stt_love.og.command_router import CommandRouter
        router = CommandRouter()
        route = router.route("/research")
        self.assertEqual(route.command, "/research")
        self.assertEqual(route.capability, "research")
        self.assertEqual(router.registry.validate(), [])

    def test_execution_state_does_not_equal_verification(self):
        from projects.LOVE.stt_love.state_semantics import assert_state_separation
        with self.assertRaises(ValueError):
            assert_state_separation(lifecycle="TESTED", execution="PASSED", verification="VERIFIED")

    def test_evidence_is_not_authority(self):
        transition = RealityTransition(
            LifecycleState.OPERATIONALIZED,
            LifecycleEvent.PRODUCTION,
            LifecycleState.PRODUCTION,
            evidence=EvidenceBoundary(("E-1",), True),
            authority=AuthorityBoundary("operator", "reality-transition", False),
        )
        with self.assertRaises(ContractError):
            validate_transition(transition)
