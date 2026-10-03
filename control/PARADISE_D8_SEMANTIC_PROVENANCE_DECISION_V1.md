# PARADISE D8 â€” Semantic Provenance Decision

Status: DESIGN DECISION / NOT SEMANTIC FREEZE
Classification: NEW DESIGN TARGET â€” UNVERIFIED

## 1. Decision

The requested PARADISE 19-invariant semantic kernel is NOT established as a historical canonical source.

Based on the read-only forensic recovery performed against the available PARADISE repository, legacy control-plane artifacts, attestation artifacts, Git history, and workspace artifacts, the 19-invariant kernel is classified as:

> UNVERIFIED NEW DESIGN TARGET

It MUST NOT be described as a recovered historical canonical source unless new provenance evidence is found.

## 2. Verified Current Baseline

The current implementation lineage is anchored at:

- Initial PARADISE baseline commit: `1142b73a4f0df4bb678a7765a50a21196ea3cb23`
- Kernel blob: `c1c5a79c102c82cb4e0e67c8ea6fb7030030b12d`
- Kernel SHA-256: `2ABEAED1655DC404E335CC26835747072C92424F7679474983FBE0C4FA60392B`
- Semantic baseline declared by the implementation contract: `7 primitives + 5 obligations + K1-K8`
- Implementation test evidence: `16/16 PASS`

The current K1-K8 baseline is provenance-bound and tested. This does not establish equivalence to a 19-invariant semantic kernel.

## 3. Semantic Lineage Boundary

The following lineage is established:

`PARADISE_CONTROL_MODEL_V1`
-> `PARADISE_IMPLEMENTATION_CONTRACT_V1`
-> `runtime/paradise_kernel.py`
-> implementation evidence / attestation

The forensic search did not recover an independent historical semantic parent containing the requested 19 invariants.

## 4. Prohibited Inference

The following claims are NOT authorized by current evidence:

- K1-K8 are eight of the 19 invariants.
- The remaining 11 invariants can be reconstructed by subtraction.
- K1-K8 are semantically equivalent to the requested 19-invariant kernel.
- Existing implementation tests verify the 19-invariant target.

No semantic reconstruction is performed by this decision record.

## 5. Evidence Interpretation

`16/16 PASS` establishes implementation-test success for the current K1-K8 baseline.

A declaration such as `semantic_change: false` establishes that the audited implementation did not change relative to its declared baseline. It does NOT establish that the baseline is historically canonical or that it contains the requested 19 invariants.

Therefore:

`implementation integrity != historical semantic canonicality`

## 6. D8 Gate State

- 7 primitives: DESIGN / ESTABLISHED
- 5 obligations: DESIGN / ESTABLISHED
- K1-K8: TESTED / PROVENANCE-BOUND
- 19 invariants: UNVERIFIED
- Forbidden-transition inventory for the 19-invariant target: UNVERIFIED
- Canonical 19-invariant provenance: NOT FOUND
- Semantic equivalence K1-K8 <-> 19: UNVERIFIED
- Semantic freeze: BLOCKED

## 7. Next Gate

Before semantic freeze, the 19-invariant target must receive an explicit semantic design and canonical authority decision. The target MUST NOT be retroactively represented as historical provenance.

This record does not modify the kernel, implementation contract, runtime, or evidence artifacts.