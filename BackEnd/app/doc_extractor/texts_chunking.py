from langchain_text_splitters import RecursiveCharacterTextSplitter
from BackEnd.app.CONFIG import CHUNKING_OVERLAP, CHUNKING_SIZE
from BackEnd.app.text_sanitizer import sanitize_text
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(
    "intfloat/multilingual-e5-base"
)
def token_length(text: str): 
    return len(
        tokenizer.encode(
            text, 
            add_special_tokens=False
        )
    )

def chunking(text: str):
    text = sanitize_text(text)

    chunker = RecursiveCharacterTextSplitter(
        chunk_size=CHUNKING_SIZE, 
        chunk_overlap=CHUNKING_OVERLAP,
        length_function=token_length,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=False
    )

    texts = chunker.split_text(text)
    return texts

if __name__ == "__main__":
    texts = """II.3. Chức năng học tập và giao diện sử dụng
Project không chỉ dừng lại ở hỏi đáp, mà còn mở rộng thành một hệ thống hỗ trợ học tập dựa
trên tài liệu. Các chức năng chính gồm:
1. Hỏi đáp trên tài liệu: Người dùng đặt câu hỏi, hệ thống truy xuất ngữ cảnh liên quan
và sinh câu trả lời có dẫn chứng.
2. Tóm tắt nội dung: Hệ thống có thể tóm tắt theo toàn bộ tài liệu, theo bộ lọc hoặc theo
một truy vấn cụ thể. Với tài liệu dài, hệ thống sử dụng chiến lược map-reduce để tổng hợp
nội dung.
3. Tạo Quiz và Flashcards: Hệ thống sinh câu hỏi trắc nghiệm và thẻ ghi nhớ từ nội dung
đã truy xuất. Output được validate để đảm bảo đúng cấu trúc và hạn chế item trùng lặp.
4. Giao diện đa nền tảng: Người dùng có thể tương tác với hệ thống qua Streamlit UI,
CLI bằng Typer hoặc REST API bằng FastAPI. Kết quả học tập có thể xuất ra JSON
hoặc Markdown để lưu trữ và chia sẻ.
II.4. Đánh giá và tối ưu hệ thống
Bên cạnh phần cài đặt, project còn có nhóm thực nghiệm nhằm đánh giá chất lượng RAG một
cách định lượng. Phần này tập trung vào hai hướng chính:
1. Đánh giá bằng Ragas: Hệ thống sử dụng bộ benchmark gồm các cặp câu hỏi và đáp
án chuẩn để đo các chỉ số như context recall, context precision, faithfulness và answer
relevancy. Các chỉ số này giúp phân tích chất lượng truy xuất và mức độ bám sát ngữ cảnh
của câu trả lời.
2. So sánh chiến lược Chunking: Project thử nghiệm nhiều cấu hình chunking khác nhau,
bao gồm recursive chunking và semantic chunking. Mỗi chiến lược được index vào một
collection Qdrant riêng để so sánh công bằng trên cùng bộ benchmark.
3. Đánh giá Reranking: Hệ thống thử nghiệm thêm bước reranking bằng cross-encoder.
Cách này truy xuất nhiều chunk ban đầu, chấm lại mức độ liên quan giữa câu hỏi và từng
chunk, sau đó chỉ đưa các chunk tốt nhất vào prompt.
Nhờ cấu trúc này, project vừa cung cấp một ứng dụng NotebookLM đơn giản có thể sử dụng
thực tế, vừa có cơ chế đánh giá để lựa chọn cấu hình retrieval phù hợp hơn cho tài liệu học tập."""

