# MyNotebook RAG Benchmark

Benchmark tài liệu thật dùng **4 PDF / 73 trang / 60 câu hỏi**. Manifest và gold
set nằm trong `datasets/documents.json` và `datasets/document_qa.json`, được quản
lý trong Git. PDF gốc trong `/home/nhminh/Documents` chỉ được đọc; corpus trích
xuất, dự đoán và kết quả chạy nằm trong các thư mục đã được bỏ qua bởi Git.

## Dữ liệu và protocol

| ID | Tài liệu | Trang |
|---|---|---:|
| survey | `s11432-025-4676-4.pdf` | 40 |
| tinyface | `bt_deeplearning_chuong6-7.pdf` | 16 |
| challenge | Báo cáo nghiên cứu AI Challenge trong `ToanKe/` | 14 |
| english | Đề ôn tập hè tiếng Anh số 1, có hướng dẫn giải | 3 |

- 10 câu `dev`, 50 câu `test`; test có 44 câu trả lời được và 6 câu thiếu dữ liệu.
- Sáu nhóm câu trả lời được: factual, paraphrase, cross_language, table_lookup,
  answer_key và multi_hop. Có thêm nhóm unanswerable.
- Mỗi câu có `id`, `split`, `category`, `question`, `reference_answer`,
  `required_facts`, `expected_abstain`, và `evidence` (document ID, trang, quote).
- Trang là số thứ tự vật lý PDF, bắt đầu từ 1. Quote được đối chiếu sau chuẩn hóa
  Unicode, hoa/thường và dấu câu. SHA-256 và số trang phải đúng manifest.
- Toàn bộ tài liệu được index, gồm các trang không được hỏi để tạo distractors.
- Dữ kiện được chấm theo tài liệu đã cung cấp, không khẳng định thông tin trong
  báo cáo nghiên cứu do AI tạo vẫn đúng ở thời điểm hiện tại.
- Gold do trợ lý biên soạn và kiểm tra quote tự động. Chưa có phản biện ngữ nghĩa
  độc lập từ người; đây là bộ đánh giá phát triển, chưa phải benchmark chuẩn hóa.
- Chỉ dùng `dev` để điều chỉnh prompt/retrieval. Không sửa ngưỡng hoặc nhãn để
  tăng điểm test. Khi sửa nhãn thực sự sai, đổi version và chạy lại baseline.

## Chạy baseline tài liệu thật

Tất cả lệnh Python phải dùng Conda `DL_Env`:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate DL_Env
python -m pytest -q Benchmark/tests BackEnd/app/tests/test_text_sanitizer.py
python Benchmark/run_benchmark.py corpus --split test --k 5 --iterations 3
```

Baseline dùng BM25 cục bộ (`k1=1.5`, `b=0.75`), không cần dịch vụ ngoài. PDF được
đọc bằng `pdftotext -layout`, không OCR. Chunking dùng đúng hàm production,
tokenizer `intfloat/multilingual-e5-base`, chunk 400 tokens, overlap 60. Tokenizer
phải đã có trong cache; runner bật chế độ Hugging Face offline và không tự cài
package/model. Poppler đã có trên máy tại thời điểm chạy.

Có thể thay đường dẫn nguồn mà không đổi dữ liệu:

```bash
python Benchmark/run_benchmark.py corpus \
  --documents-dir /YOUR_DOCUMENT_DIRECTORY --split dev --k 5
```

Để CI trả mã 1 khi không đạt ngưỡng recall 0.75:

```bash
python Benchmark/run_benchmark.py corpus --split test --k 5 --fail-on-threshold
```

Kết quả JSON/Markdown nằm trong `results/`. `workspace/chunks.json` chứa ID ổn
định dạng `survey:p9:c1`, nội dung, document ID và trang. Đây là artifact cục bộ
được bỏ qua bởi Git; không commit corpus hay tài liệu gốc. Bộ báo cáo lưu lại hash
manifest/dataset, Python, platform, số vòng đo, thời gian từng tài liệu và ranking.

## Kết quả đã thực chạy

Baseline ngày **08/10/2026**, CPU, split test, k=5, ba vòng đo:

| Chỉ số | Kết quả |
|---|---:|
| Documents / pages / chunks | 4 / 73 / 275 |
| Page Hit Rate@5 | 0.8409 |
| Page Recall@5 | 0.7159 |
| Page Precision@5 | 0.1727 |
| MRR@5 | 0.7534 |
| Page nDCG@5 | 0.6781 |
| Exact quote coverage@5 | 0.7045 |
| Warm mean / p95 | 0.1138 / 0.1959 ms |

Ngưỡng recall 0.75 **FAIL**; sinh câu trả lời **SKIP**. Xem
[baseline đầy đủ](baselines/corpus-bm25-20261008.md) và phần benchmark trong
[README project](../README.md). Không thay baseline này bằng điểm 1.00 từ ba đoạn
fixture cũ. Chênh lệch ngôn ngữ và câu tổng hợp nhiều bằng chứng là các nhóm yếu
trong BM25; bảng phân nhóm được giữ nguyên trong báo cáo.

## Định nghĩa chỉ số

- Retrieval chỉ chấm câu có gold evidence. Recall là tỷ lệ trang gold xuất hiện
  trong top-k **chunks**. Hit Rate là có ít nhất một trang gold.
- Precision chia số trang gold khác nhau tìm được cho k. Chunks trùng trang vẫn
  chiếm vị trí nhưng không được cộng điểm thêm. MRR/nDCG dùng các vị trí đó,
  không nén ranking để làm đẹp kết quả; MRR bị cắt ở k.
- Một trang đúng có thể chứa chunk sai ý. `evidence_coverage` yêu cầu quote gold
  xuất hiện trong một chunk đã lấy từ đúng trang; mỗi bằng chứng được chấm riêng.
  Quote vượt ranh giới chunk có thể không được tính dù trang đã truy xuất đúng.
- EM/token F1 so sánh với đáp án ngắn chuẩn. `fact_coverage` kiểm tra từng cụm từ
  chuẩn theo biên token, không đánh giá ngữ nghĩa hay diễn đạt tương đương.
- Faithfulness là **lexical proxy**, tỷ lệ token câu trả lời xuất hiện trong ngữ
  cảnh thực sự truy xuất. Nó không chứng minh entailment và không dùng làm
  semantic release gate. `answer_relevancy` cũ chỉ là alias F1 nên không báo lại.
- Citation precision/recall đánh giá đúng trang gold và nguồn đã truy xuất, chưa
  chứng minh từng mệnh đề được nguồn hỗ trợ. Citation không tồn tại bị mất điểm.
- Abstention chỉ tính trên câu thiếu dữ liệu; tách riêng tỷ lệ không từ chối nhầm
  trên câu trả lời được. Nhận diện từ chối bằng cụm từ, cần người kiểm tra bổ sung.
- Corpus preparation bao gồm import tokenizer và trích xuất/chunking; index build
  tách riêng. Warm latency loại request đầu và một warm-up; QPS là tuần tự, không
  phải throughput API hay tải concurrent. Không xóa cache hệ điều hành/model.

## Đo embedding production

```bash
python Benchmark/run_benchmark.py corpus --backend cloudflare-dense \
  --split test --k 5 --iterations 3
```

Dùng adapter BGE-M3 thật của backend và cosine search cục bộ. Cần `CF_API_KEY` và
`CF_ACC_ID`, lấy từ môi trường hoặc `BackEnd/.env`. Không in/ghi credentials vào
report. Lệnh này gửi toàn bộ chunk và câu hỏi tới Cloudflare Workers AI, có thể
phát sinh phí; chỉ chạy khi sẵn sàng gửi tài liệu. Không dùng GPU cục bộ và không
thay thế phép đo hybrid Qdrant BM25/RRF. Đường chạy này chưa được thực thi.

## Chấm đầu ra RAG đã xuất

Sau khi chạy corpus, ánh xạ ngữ cảnh/citation của adapter về ID trong
`workspace/chunks.json`, rồi lưu JSON array gồm **đầy đủ ID của split**:

```json
[
  {
    "id": "survey-03",
    "answer": "Multimodal understanding and generation.",
    "retrieved_ids": ["survey:p1:c3"],
    "cited_ids": ["survey:p1:c3"]
  }
]
```

Ví dụ trên chỉ minh họa schema; một dòng không đủ chạy split test 50 câu. Lưu file
trong `Benchmark/workspace/`, rồi chạy:

```bash
python Benchmark/run_benchmark.py corpus --split test --k 5 \
  --predictions Benchmark/workspace/predictions.json
```

Runner từ chối thiếu/thừa/trùng case ID, chunk ID không tồn tại, context/citation
ID trùng. Ngữ cảnh lấy từ corpus đã xác minh, không dùng đáp án chuẩn làm câu trả
lời dự đoán. Không tự điền câu thiếu hoặc giả lập LLM. Report nêu rõ provenance
chạy mô hình do bên xuất dự đoán cung cấp, không xác minh execution độc lập.

## Đo API hiện tại với session và native citations

1. Khởi động API/Qdrant với dependencies đã khai báo trong `BackEnd/pyproject.toml`.
2. Đăng nhập bằng tài khoản benchmark chuyên dụng. Qua UI, tạo chat riêng và upload
   đúng bốn PDF trong manifest; chờ index hoàn tất. Không dùng chat cá nhân hiện có.
3. Sao chép `document_api.example.toml` thành `config.toml` (đã được bỏ qua bởi Git),
   điền `user_id` và `chat_id`. Credentials chỉ đưa qua biến môi trường.
4. Chạy:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate DL_Env
# Set BENCHMARK_USERNAME and BENCHMARK_PASSWORD securely in this shell.
python Benchmark/run_document_api.py --config Benchmark/config.toml --split test --k 5
```

Runner login qua `/auth/login`, giữ cookie trong bộ nhớ, gửi `include_sources=true`
đến `/documents/retrieval/stream` và đọc `sources`, `token`, `citations`, `error`,
`done`. Không cần khóa trace nội bộ. Filename ánh xạ về manifest; page/source
không xác định không nhận điểm. TTFT tính từ trước request tới token không rỗng
đầu tiên, bao gồm thời gian chờ HTTP headers. Không có token thì TTFT không được
tính. Errors/missing done/empty answer làm request FAIL; request success gate 1.0.

Chat chung tạo phép đo **sequential có history**: câu sau có thể bị ảnh hưởng bởi
summary/câu trước. Để kiểm thử độc lập, cấu hình `[document_api.case_chat_ids]` với
chat riêng đã index đủ 4 PDF cho **mỗi** câu trong split. Runner yêu cầu đủ ID và
không trùng chat. Các chat phải chưa có lịch sử benchmark; runner không xóa lịch
sử. Không chạy lặp lại cùng chat nếu muốn coi là independent evaluation.

Report lưu native nguồn/citation, câu trả lời và lỗi từng câu. API writes chat
history và gọi dịch vụ LLM/embedding theo cấu hình backend. Latency là các stream
HTTP thành công, không phân loại cold/warm. Answer quality loại request exception;
báo `scored_cases` và request failures riêng để không gọi một run thiếu là pass.

**Chưa đo E2E:** API health trên máy trả HTTP 000; `DL_Env` thiếu `pymupdf`,
`qdrant_client`, `fastembed`. Không cài dependency tự động. Tests parser/scorer dùng
SSE giả lập chỉ xác minh logic benchmark, không được tính là live result.

## Smoke suites trước đây

```bash
python Benchmark/run_benchmark.py offline
python Benchmark/run_benchmark.py local
python Benchmark/run_benchmark.py live --config Benchmark/config.example.toml
```

Các suite cũ vẫn được giữ để tương thích. `offline` là component smoke test;
`local` còn dùng fixture ba đoạn và router; embedding module hiện là Cloudflare,
không còn mô hình VietRAG local. Suite `live` cũ không có session cookie theo auth
hiện tại, chỉ upload một TXT fixture và không đọc sources: dùng
`run_document_api.py` cho benchmark corpus thật. Không coi những suite này phủ hết
pipeline hiện tại. Xem [COVERAGE.md](COVERAGE.md).

## Review bổ sung trước release

Người review cần đọc đáp án và các trích đoạn thực truy xuất, chấm riêng: đủ ý,
không thêm sự kiện không có bằng chứng, citation hỗ trợ đúng mệnh đề, từ chối đúng
khi thiếu dữ liệu. Lưu quyết định/reason theo case ID. Không dùng lexical proxy
thay review ngữ nghĩa; không dùng test để chọn cấu hình. So sánh run chỉ khi cùng
hash corpus/dataset, split, k, backend, máy và protocol history. Ngưỡng 0.75 recall
và 0.80 fact/abstention là điểm khởi đầu, cần định SLO bằng dev trước test cuối.
