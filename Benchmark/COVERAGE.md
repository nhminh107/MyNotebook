# Coverage matrix

| Capability | Corpus BM25 | Corpus Cloudflare dense | Document API | Existing smoke suites |
|---|---|---|---|---|
| 4 PDF hashes / 73 pages / gold quotes | Verified | Same validation | Same local validation | Synthetic fixtures |
| Production recursive tokenizer/chunking | Executed | Same function | Backend ingestion, prepared separately | Local extractor fixture |
| Production PDF extractor / OCR | No; Poppler text layers | No; Poppler text layers | Through prior upload | Local suite requires PDF packages |
| Retrieval ranking | Lexical baseline executed | Local cosine, not executed | Native source pages; not executed | Local 3-passage fixture |
| Dense + BM25 + RRF in Qdrant | No | No | Through backend, not executed | Legacy live implicit |
| Page recall/precision/MRR/nDCG | Executed | Implemented | Recall from native source pages | Synthetic metric checks |
| Exact gold quote coverage | Executed | Implemented | Per-case native evidence | No |
| EM/F1/facts / lexical faithfulness | Exported predictions only | Exported predictions only | Implemented, not executed | Fixture or legacy live |
| Native citations + session login | No | No | Implemented; parser unit-tested | Legacy live has no cookie support |
| Negative abstention | Requires exported answers | Requires exported answers | Implemented, not executed | Synthetic answer examples |
| TTFT / total SSE latency | No | No | Implemented, not executed | Legacy SSE endpoint |
| Warm latency / sequential QPS | Executed | Implemented | Per-request latency only | Legacy concurrent load |
| Source/chat isolation | No | No | Per-case pre-indexed chats optional; not isolation security test | Separate backend tests |
| Agent, math, web, OCR tools | No | No | No | Legacy agent smoke only |
| Semantic faithfulness / citation entailment | Human review pending | Human review pending | Human review pending | Not measured |

`BackEnd/app/pipeline.py` now emits native `sources` and protected
`retrieval_trace` events. The previous statement that chunk IDs/pages are not
observable is obsolete. The new API benchmark consumes sources without requiring
trace access. Native Qdrant chunk IDs differ from the stable local corpus IDs;
API evaluation maps exact filenames and physical page numbers rather than
pretending the two ID spaces are identical.

The measured corpus baseline is **not** a production hybrid retrieval or LLM
score. API execution is pending because the server was unavailable. A complete
benchmark harness and gold dataset do not imply every supported execution mode
has been measured. Skipped components and failing quality gates stay visible.
