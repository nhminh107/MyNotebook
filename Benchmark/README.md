# MyNotebook RAG Benchmark

Bộ benchmark này đánh giá cả **chất lượng** và **hiệu năng** của MyNotebook. Nó
không cần thêm dependency: mọi lệnh đều chạy bằng `BackEnd/.venv/bin/python`.

## Phạm vi

| Nhóm | Chỉ số / kiểm tra |
|---|---|
| Retrieval | Hit Rate@k, Recall@k, Precision@k, MRR, nDCG@k |
| Answer | Exact Match, token F1, fact coverage, faithfulness, answer relevancy, abstention accuracy |
| Performance | cold time, warm-up time, warm mean/p50/p95/p99, TTFT, total latency, throughput, peak RSS |
| Ingestion | extractor/factory, sanitizer, FAISS add/search/rollback, upload end-to-end |
| RAG | retrieve + streamed answer + conversation summary/history |
| Agent | quyền Free/Pro, document tool, web/math/OCR qua agent endpoint |
| API/Auth | health, validation, SSE contract, upload type validation, chat history, register/login (opt-in) |
| Isolation | user/chat isolation được kiểm tra bằng case `negative_query` trong live dataset |

Xem [COVERAGE.md](COVERAGE.md) để biết mapping chi tiết giữa chức năng và suite,
cùng các giới hạn quan sát hiện tại của API.

`offline` là smoke benchmark xác định (deterministic), dùng code thật của ứng dụng
cho sanitizer, SSE formatter và FAISS. `live` gọi API đang chạy và là kết quả cần
dùng để đánh giá hệ thống RAG thực tế. Những phần chưa cấu hình sẽ là `SKIP`, không
được tính là pass.

Lưu ý: API hiện trả context đã nối thành chuỗi, không trả chunk ID/score. Vì vậy
Recall/MRR/nDCG của retriever được đo trong suite `local` trên embedding + FAISS;
suite `live` đo answer quality và groundedness trên corpus fixture. Muốn đo chính
xác hybrid Qdrant end-to-end theo chunk ID, API cần bổ sung trace retrieval chỉ dành
cho benchmark hoặc adapter đọc Qdrant với cùng filter `user_id/chat_id`.

## Chạy nhanh

Từ thư mục gốc dự án:

```bash
BackEnd/.venv/bin/python Benchmark/run_benchmark.py offline
```

Đo model embedding thật, retrieval accuracy và query-router (chỉ dùng model đã
có trong cache, không tự tải dependency/model):

```bash
BackEnd/.venv/bin/python Benchmark/run_benchmark.py local
```

Kết quả nằm trong `Benchmark/results/` dưới dạng JSON và Markdown.

Chạy test framework benchmark:

```bash
BackEnd/.venv/bin/python -m pytest -q Benchmark/tests
```

## Benchmark live end-to-end

1. Chạy Qdrant, cấu hình Supabase/LLM trong backend và khởi động API.
2. Sao chép cấu hình và chỉnh `user_id`; user phải tồn tại trong DB.
3. Chạy benchmark.

```bash
cp Benchmark/config.example.toml Benchmark/config.toml
BackEnd/.venv/bin/python Benchmark/run_benchmark.py live \
  --config Benchmark/config.toml \
  --dataset Benchmark/datasets/live_rag.jsonl
```

Để benchmark tải đồng thời:

```bash
BackEnd/.venv/bin/python Benchmark/run_benchmark.py live \
  --config Benchmark/config.toml --concurrency 4 --iterations 10
```

`--include-auth` tạo một tài khoản benchmark ngẫu nhiên rồi kiểm tra register/login.
Đây là thao tác ghi dữ liệu nên mặc định tắt. `--skip-upload` dùng khi chat đã được
index sẵn. `--fail-on-threshold` trả exit code 1 nếu có ngưỡng chất lượng/latency
không đạt, phù hợp CI.

## Dataset

Mỗi dòng JSONL là một case:

```json
{"id":"q1","question":"...","reference_answer":"...","required_facts":["..."],"relevant_ids":["chunk-1"],"mode":"rag"}
```

- `required_facts`: các cụm ý bắt buộc, dùng cho fact coverage.
- `relevant_ids`: ID chunk chuẩn, dùng cho Recall/MRR/nDCG khi adapter trả IDs.
- `mode`: `rag`, `agent`, `router`, hoặc `negative_query`.
- `expected_abstain`: câu hỏi ngoài tài liệu phải từ chối/khẳng định thiếu dữ liệu.
- `expected_route`: nhãn chuẩn của query router.

Dataset mẫu live đi cùng `fixtures/benchmark_knowledge.txt`. Hãy thay bằng gold set
thực tế (nên tối thiểu 50–100 câu, có câu paraphrase, multi-hop, ngoài tài liệu và
phân tách theo từng loại tài liệu). Không dùng cùng câu để tinh chỉnh prompt và báo
cáo test cuối.

## Diễn giải cold/warm

- `cold_start_ms`: import/khởi tạo hoặc request đầu tiên trong tiến trình hiện tại.
- `warmup_ms`: các lượt warm-up bị loại khỏi thống kê.
- `warm_latency_ms`: các lượt sau warm-up; báo mean/p50/p95/p99.
- `ttft_ms`: time-to-first-token của SSE.
- `throughput_qps`: số request hoàn thành / wall-clock time của batch concurrent.

Cold start tuyệt đối nên chạy trong container/VM mới. Lệnh này đo cold trong tiến
trình benchmark, không xóa cache hệ điều hành hay cache model.

## Ngưỡng mặc định

Ngưỡng nằm trong `config.example.toml`. Đây là baseline khởi đầu, không phải chuẩn
phổ quát. Sau 3–5 lần chạy ổn định trên cùng máy, lưu một baseline và đặt ngưỡng
theo SLO sản phẩm. So sánh kết quả chỉ hợp lệ khi dataset, model, cấu hình retrieval,
máy và mức concurrency giống nhau.
