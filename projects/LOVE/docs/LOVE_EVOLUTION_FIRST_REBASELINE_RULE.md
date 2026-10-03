# LOVE Evolution-First Rebaseline Rule

## Status
DESIGN / FEATURE-BRANCH GOVERNANCE RULE.
Not a runtime authority, not a self-escalation mechanism, and not a release gate by itself.

## Purpose
LOVE evolves from the best verified current baseline rather than preserving legacy merely because it once existed.

## Core rule
For a required capability, contract, or semantic owner:

1. Search the current canonical source/evidence independently up to three times using materially different lookup paths when practical.
2. If sufficient current evidence is still not found after three attempts, treat the item as a **baseline GAP** for engineering purposes.
3. Do not claim that the item never existed historically. The conclusion is only that the current baseline does not provide sufficient evidence to depend on it.
4. A baseline GAP may be replaced or newly designed using a best-fit solution without reconstructing legacy implementation.
5. If an existing implementation is found but is obsolete, unsafe, redundant, semantically colliding, or materially inferior to a better-fit alternative, it may be REPLACE/RETIRE candidate.

## Decision order
FOUND + good fit + evidence -> KEEP
FOUND + useful but incomplete -> RECONCILE / EXTEND
FOUND + obsolete or materially inferior -> REPLACE
FOUND + duplicate/collision -> RECONCILE or REPLACE
NOT FOUND after three searches -> GAP -> CREATE/REPLACE candidate

## Non-duplication rule
A GAP does not authorize creation of a new subsystem automatically. Before CREATE, check whether an existing semantic owner or contract can safely own the required behavior.

## Best-fit rule
Selection considers:
- fitness for LOVE's goals and architecture;
- simplicity;
- reliability;
- security;
- evidenceability;
- operability;
- maintainability;
- runtime verifiability.

Best-in-class alone is insufficient.

## Evidence rule
Implementation decisions remain subject to evidence. The normal progression is:
DESIGN -> IMPLEMENT -> REGRESSION -> NEGATIVE TEST -> EVIDENCE -> VERIFY.

Unverified implementation is not treated as verified capability.

## Authority boundary
This rule does not grant autonomous authority to:
- merge main;
- release production;
- change governance/security gates;
- convert evidence into authority;
- self-promote capabilities;
- create versions without explicit project direction.

## Legacy boundary
Historical artifacts may inform comparison when explicitly available, but they are not substitutes for current canonical source evidence. Legacy reconstruction is not a default recovery strategy.

## Application to the current rebaseline
Current evidence-supported decisions are recorded separately in the rebaseline gap register. Items that remain unresolved after the three-look rule are treated as baseline gaps rather than subjects for indefinite archaeology.
