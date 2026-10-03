# LOVE source provenance contract

The deployment environment must inject these variables; the runtime never runs git to infer them.

- LOVE_SOURCE_COMMIT = exact source commit used for the deployment
- LOVE_SOURCE_TREE_SHA = exact Git tree SHA for that commit
- LOVE_EVIDENCE_HASH = SHA-256 of the deployment evidence bundle or manifest

The /api/v1/provenance response keeps declared provenance separate from observed runtime hashes. A matching declared value is not labeled VERIFIED unless an independent replay proves it.
