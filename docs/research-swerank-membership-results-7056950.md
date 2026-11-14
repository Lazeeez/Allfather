# Retained SweRank corpus membership: verified PACE result

The archive from PACE job 7056950 has been received and verified locally. Every saved
prediction ID is present in the supplied retained exports, including every identifier
recovered by the import correction. This closes the retained-export membership check;
it does not prove unique declaration identity or historical inference-byte provenance.

## Verified evidence

- [Original transferred archive](../results/research/corrections/pace-swerank-membership-7056950.tar.gz):
  934,601 bytes; SHA256 `370e79d650dc472d8d93cc5421e4d39334aaeebe382e3bb7c1d8bdaf21c51665`.
- [Local verification](../results/research/corrections/swerank-membership-verification-v1.json):
  four source fingerprints, 16 original/corrected prediction hashes, nine output hashes,
  all eight run summaries and 1,160 corpus-evidence records checked.
- Every correction reproduces from the original saved predictions. Every slot, recovered
  flag, document ID and multiplicity agrees with the corresponding corpus evidence.
- Short- and full-report corpus hashes match for all 580 paired issue snapshots.

One local historical audit file uses CRLF line endings while its Git blob and PACE copy
use LF. The verifier checked the exact committed blob against PACE and proved that the
working-copy difference is only CRLF versus LF. Both hashes and the Git revision are
recorded. The historical working copy was not rewritten, and semantic differences would
fail verification.

## Membership counts

All eight runs have their full expected issue counts, with no missing IDs or unavailable
corpora. Counts below are prediction slots, not independent observations or unique issues.
Agent subsets reuse issues from the full runs; models and report conditions also repeat IDs.

| Condition | Model | Issues | Slots | Ambiguous slots | Recovered slots | Ambiguous recovered |
|---|---|---:|---:|---:|---:|---:|
| Short, agent subset | Large | 198 | 1,980 | 37 | 154 | 1 |
| Short, agent subset | Small | 198 | 1,980 | 44 | 153 | 2 |
| Full, agent subset | Large | 198 | 1,980 | 37 | 158 | 2 |
| Full, agent subset | Small | 198 | 1,980 | 38 | 152 | 2 |
| Full, all | Large | 580 | 5,800 | 82 | 439 | 2 |
| Full, all | Small | 580 | 5,800 | 68 | 434 | 4 |
| Short, all | Large | 580 | 5,800 | 78 | 431 | 2 |
| Short, all | Small | 580 | 5,800 | 76 | 425 | 5 |
| Total across saved runs | | 3,112 | 31,120 | 460 | 2,346 | 20 |

Of 31,120 slots, 30,660 map to an ID occurring once in the export and 460 map to repeated
IDs. Of 2,346 recovered slots, 2,326 have unique exported IDs and 20 have repeated IDs.
The recovered slots represent 790 distinct issue/document-ID pairs. The 20 ambiguous
recovered slots reduce to six such pairs across four issues, all in `thedotmack/claude-mem`:

| PR | Export path / name | Occurrences in that corpus |
|---|---|---:|
| 5084 | `plugin/scripts/worker-service.cjs/prepareSessionExtras` | 4 |
| 3709 | `plugin/scripts/worker-service.cjs/execute` | 7 |
| 5084 | `plugin/scripts/worker-service.cjs/execute` | 13 |
| 3878 | `plugin/scripts/worker-service.cjs/execute` | 7 |
| 4483 | `plugin/scripts/mcp-server.cjs/emptyStr` | 2 |
| 3878 | `plugin/scripts/worker-service.cjs/i` | 35 |

These are corpus multiplicities, not assertions about causal faults, erroneous labels,
or the reason the extractor produced duplicate names. Membership in a retained corpus
does not choose one of the declarations sharing an ID.

## Scope and next step

The import repair now has more evidence than a syntactic round trip: the recovered IDs
exist in the retained baseline corpora. This audit does not rerun models, rescore outcomes,
remove labels, or strengthen the withdrawn superiority claim. Existing score artifacts
remain unchanged.

Corpus bytes and index files were not transferred, so local verification checks the PACE
record's hashes, joins and internal consistency rather than independently rescanning the
exports. Historical inference did not pin corpus hashes; this limitation remains even
after successful retained-export verification. Full causal gold validation and parser
coverage are separate work.

No repeat PACE job is required for this check. Independent initial reviews and adjudication
remain the next study dependency; the broader 95-case sample is still unannotated.

Validation: all 341 Python tests pass, including rejection of altered membership slots,
omitted slots, duplicate rows, unsafe archive entries and unproved line-ending changes.
Ruff lint and formatting checks pass for the verifier and its tests.

To reproduce the local verification without extracting the archive or overwriting evidence:

```bash
python scripts/verify_swerank_membership.py \
  --archive results/research/corrections/pace-swerank-membership-7056950.tar.gz \
  --out reports/swerank-membership-verification-repeat.json
```
