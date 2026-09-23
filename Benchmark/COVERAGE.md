# Coverage matrix

| Application capability | Offline | Local models | Live E2E |
|---|---:|---:|---:|
| Text sanitizer | ✓ | — | implicit |
| PDF/DOCX/TXT extraction + chunking | — | ✓ | TXT upload |
| VietRAG embedding cold/warm | — | ✓ | implicit |
| FAISS add/search/persist/rollback | ✓ | ✓ retrieval | — |
| Hybrid Qdrant (dense + BM25 + RRF) | — | — | implicit through upload/query |
| Retrieval accuracy | metric validation | Hit/Recall/MRR | corpus-grounded answer |
| Query router | — | accuracy + latency | — (router is not wired to API) |
| Standard RAG streaming | SSE contract | — | answer metrics + TTFT/latency |
| Summary/chat history | — | — | history after multiple turns |
| Agent and Pro authorization | — | — | agent SSE outcome |
| Document/web/math/OCR tools | — | — | agent endpoint; exact tool trace unavailable |
| Register/login | — | — | opt-in (`--include-auth`) |
| API validation/health | SSE formatting | — | ✓ |
| User/chat isolation | — | — | dataset fact check; exact retrieval trace unavailable |
| Concurrent load | — | — | QPS + p50/p95/p99 |

Hai khoảng trống do kiến trúc API hiện tại:

1. `QDrant.search()` chỉ trả một chuỗi context, không trả chunk ID và score, nên live
   Recall@k/MRR/nDCG không thể tính chính xác.
2. Agent stream không trả tool trace, nên benchmark chỉ xác nhận kết quả/stream chứ
   không thể chứng minh tool cụ thể đã được gọi.

Không nên bật trace này cho người dùng cuối. Nếu cần release gate chặt hơn, thêm một
adapter benchmark nội bộ trả `{chunk_id, score, tool_name, duration_ms}`.

