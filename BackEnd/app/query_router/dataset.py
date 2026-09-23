# BackEnd/app/query_router/dataset.py


DIRECT_QUERIES = [

    # ============================================================
    # PYTHON
    # ============================================================

    "Python là gì?",
    "Python dùng để làm gì?",
    "Giải thích Python.",
    "Bạn có thể giải thích Python không?",
    "Python hoạt động như thế nào?",
    "Python có đặc điểm gì?",
    "Tại sao Python phổ biến?",
    "Python thường được sử dụng trong những lĩnh vực nào?",
    "Python có những kiểu dữ liệu nào?",
    "Python có dễ học không?",
    "Python khác C++ như thế nào?",
    "Python dùng để lập trình web được không?",
    "Python có thể dùng cho machine learning không?",
    "Python có phải ngôn ngữ lập trình không?",
    "Cho tôi biết về Python.",
    "Tôi muốn tìm hiểu Python.",
    "Python có ưu điểm gì?",
    "Python có nhược điểm gì?",

    # ============================================================
    # C++
    # ============================================================

    "C++ là gì?",
    "C++ dùng để làm gì?",
    "Giải thích về C++.",
    "C++ hoạt động như thế nào?",
    "C++ có đặc điểm gì?",
    "C++ khác Python như thế nào?",
    "C++ có thể dùng để lập trình game không?",
    "C++ có phải ngôn ngữ lập trình hướng đối tượng không?",
    "Tại sao C++ được sử dụng nhiều?",
    "Cho tôi biết về C++.",
    "C++ có những kiểu dữ liệu nào?",
    "C++ dùng trong những lĩnh vực nào?",

    # ============================================================
    # FASTAPI
    # ============================================================

    "FastAPI là gì?",
    "FastAPI dùng để làm gì?",
    "Giải thích FastAPI.",
    "FastAPI hoạt động như thế nào?",
    "FastAPI có ưu điểm gì?",
    "FastAPI có dùng để xây dựng REST API không?",
    "FastAPI khác Flask như thế nào?",
    "FastAPI có phù hợp để xây dựng backend không?",
    "Cho tôi biết về FastAPI.",
    "FastAPI hỗ trợ Python đúng không?",
    "FastAPI có nhanh không?",
    "FastAPI thường được dùng trong trường hợp nào?",

    # ============================================================
    # QDRANT
    # ============================================================

    "Qdrant là gì?",
    "Qdrant dùng để làm gì?",
    "Giải thích Qdrant.",
    "Qdrant hoạt động như thế nào?",
    "Qdrant có phải vector database không?",
    "Qdrant dùng trong RAG để làm gì?",
    "Tại sao cần Qdrant?",
    "Qdrant lưu dữ liệu gì?",
    "Qdrant có thể tìm kiếm vector không?",
    "Cho tôi biết về Qdrant.",
    "Qdrant khác database SQL như thế nào?",
    "Qdrant có dùng cho semantic search không?",

    # ============================================================
    # RAG
    # ============================================================

    "RAG là gì?",
    "RAG dùng để làm gì?",
    "Giải thích RAG.",
    "RAG hoạt động như thế nào?",
    "RAG có phải là fine-tuning không?",
    "RAG khác fine-tuning như thế nào?",
    "Tại sao người ta sử dụng RAG?",
    "RAG có liên quan đến vector database không?",
    "RAG có giúp giảm hallucination không?",
    "Cho tôi biết về RAG.",
    "RAG thường được dùng trong những ứng dụng nào?",
    "RAG pipeline gồm những bước nào?",

    # ============================================================
    # EMBEDDING
    # ============================================================

    "Embedding là gì?",
    "Embedding dùng để làm gì?",
    "Giải thích embedding.",
    "Embedding hoạt động như thế nào?",
    "Text embedding là gì?",
    "Embedding có liên quan đến vector không?",
    "Tại sao cần embedding trong semantic search?",
    "Embedding được sử dụng trong RAG như thế nào?",
    "Embedding model là gì?",
    "Cho tôi biết về embedding.",
    "Embedding có thể biểu diễn văn bản thành vector không?",
    "Embedding khác keyword search như thế nào?",

    # ============================================================
    # VECTOR DATABASE
    # ============================================================

    "Vector database là gì?",
    "Vector database dùng để làm gì?",
    "Giải thích vector database.",
    "Vector database hoạt động như thế nào?",
    "Tại sao cần vector database?",
    "Vector database khác SQL database như thế nào?",
    "Vector database có dùng để semantic search không?",
    "Vector database lưu vector như thế nào?",
    "Cho tôi biết về vector database.",
    "Vector database được sử dụng trong RAG như thế nào?",

    # ============================================================
    # MACHINE LEARNING
    # ============================================================

    "Machine Learning là gì?",
    "Machine Learning dùng để làm gì?",
    "Giải thích Machine Learning.",
    "Machine Learning hoạt động như thế nào?",
    "Machine Learning khác lập trình truyền thống như thế nào?",
    "Machine Learning có những loại nào?",
    "Supervised Learning là gì?",
    "Unsupervised Learning là gì?",
    "Classification là gì?",
    "Regression là gì?",
    "Cho tôi biết về Machine Learning.",
    "Machine Learning được ứng dụng ở đâu?",

    # ============================================================
    # LOGISTIC REGRESSION
    # ============================================================

    "Logistic Regression là gì?",
    "Logistic Regression dùng để làm gì?",
    "Giải thích Logistic Regression.",
    "Logistic Regression có phải machine learning không?",
    "Logistic Regression dùng cho classification được không?",
    "Logistic Regression hoạt động như thế nào?",
    "Logistic Regression khác Linear Regression như thế nào?",
    "Cho tôi biết về Logistic Regression.",

    # ============================================================
    # ALGORITHMS
    # ============================================================

    "Binary Search là gì?",
    "Binary Search dùng để làm gì?",
    "Giải thích Binary Search.",
    "Binary Search hoạt động như thế nào?",
    "Độ phức tạp của Binary Search là gì?",
    "BFS là gì?",
    "DFS là gì?",
    "BFS dùng để làm gì?",
    "DFS dùng để làm gì?",
    "Dijkstra là gì?",
    "Dijkstra dùng để làm gì?",
    "Giải thích thuật toán Dijkstra.",
    "Quick Sort là gì?",
    "Merge Sort là gì?",
    "Heap Sort là gì?",
    "Quick Sort hoạt động như thế nào?",
    "Merge Sort hoạt động như thế nào?",

    # ============================================================
    # DATA STRUCTURES
    # ============================================================

    "Stack là gì?",
    "Queue là gì?",
    "Stack dùng để làm gì?",
    "Queue dùng để làm gì?",
    "Stack khác Queue như thế nào?",
    "Linked List là gì?",
    "Linked List dùng để làm gì?",
    "Hash Table là gì?",
    "Hash Table hoạt động như thế nào?",
    "Binary Search Tree là gì?",
    "BST dùng để làm gì?",
    "AVL Tree là gì?",
    "AVL Tree hoạt động như thế nào?",
    "Cho tôi biết về Hash Table.",
    "Cho tôi biết về AVL Tree.",

    # ============================================================
    # DATABASE / SQL
    # ============================================================

    "SQL là gì?",
    "SQL dùng để làm gì?",
    "Database là gì?",
    "Database dùng để làm gì?",
    "SQL khác NoSQL như thế nào?",
    "Primary Key là gì?",
    "Foreign Key là gì?",
    "Normalization là gì?",
    "JOIN trong SQL là gì?",
    "SELECT trong SQL dùng để làm gì?",
    "Index trong database là gì?",
    "Cho tôi biết về database.",

    # ============================================================
    # DOCKER
    # ============================================================

    "Docker là gì?",
    "Docker dùng để làm gì?",
    "Giải thích Docker.",
    "Docker hoạt động như thế nào?",
    "Docker container là gì?",
    "Docker image là gì?",
    "Docker khác máy ảo như thế nào?",
    "Tại sao sử dụng Docker?",
    "Cho tôi biết về Docker.",
    "Docker có dùng để triển khai ứng dụng không?",

    # ============================================================
    # GIT
    # ============================================================

    "Git là gì?",
    "Git dùng để làm gì?",
    "Git merge là gì?",
    "Git branch là gì?",
    "Git commit là gì?",
    "Git pull là gì?",
    "Git push là gì?",
    "Git khác GitHub như thế nào?",
    "Giải thích Git.",
    "Cho tôi biết về Git.",

    # ============================================================
    # GENERAL KNOWLEDGE
    # ============================================================

    "2 cộng 2 bằng bao nhiêu?",
    "Thủ đô của Việt Nam là gì?",
    "HTTP là gì?",
    "HTTPS là gì?",
    "API là gì?",
    "REST API là gì?",
    "JSON là gì?",
    "JWT là gì?",
    "JWT dùng để làm gì?",
    "Authentication là gì?",
    "Authorization là gì?",
    "Cache là gì?",
    "CPU là gì?",
    "RAM là gì?",
]


RETRIEVE_QUERIES = [

    # ============================================================
    # PYTHON
    # ============================================================

    "Trong tài liệu của tôi, Python được giải thích như thế nào?",
    "Theo note của tôi, Python là gì?",
    "Tài liệu của tôi nói gì về Python?",
    "Tìm trong tài liệu của tôi thông tin về Python.",
    "Trong các note của tôi có đề cập đến Python không?",
    "Theo tài liệu tôi đã upload, Python được sử dụng như thế nào?",
    "Tìm phần nói về Python trong tài liệu của tôi.",
    "Trong note của tôi, Python có những đặc điểm gì?",
    "Tài liệu tôi lưu giải thích Python như thế nào?",
    "Theo các tài liệu của tôi, Python được dùng để làm gì?",

    # ============================================================
    # C++
    # ============================================================

    "Trong tài liệu của tôi, C++ được giải thích như thế nào?",
    "Theo note của tôi, C++ là gì?",
    "Tài liệu của tôi nói gì về C++?",
    "Tìm trong tài liệu của tôi phần nói về C++.",
    "Trong note của tôi, C++ được sử dụng như thế nào?",
    "Theo tài liệu tôi đã upload, C++ có những đặc điểm gì?",
    "Tài liệu của tôi giải thích C++ như thế nào?",

    # ============================================================
    # FASTAPI
    # ============================================================

    "Trong tài liệu của tôi, FastAPI được cấu hình như thế nào?",
    "Theo note của tôi, FastAPI được sử dụng để làm gì?",
    "Tài liệu của tôi nói gì về FastAPI?",
    "Tìm trong tài liệu của tôi phần liên quan đến FastAPI.",
    "Trong project của tôi, tài liệu nói FastAPI hoạt động như thế nào?",
    "Theo tài liệu đã upload, FastAPI được sử dụng ra sao?",
    "Note của tôi có đề cập đến FastAPI không?",
    "Tìm thông tin về FastAPI trong các tài liệu của tôi.",

    # ============================================================
    # QDRANT
    # ============================================================

    "Trong tài liệu của tôi, Qdrant được giải thích như thế nào?",
    "Theo note của tôi, Qdrant dùng để làm gì?",
    "Tài liệu của tôi nói gì về Qdrant?",
    "Tìm trong tài liệu của tôi thông tin về Qdrant.",
    "Trong tài liệu tôi upload, Qdrant lưu vector như thế nào?",
    "Theo các note của tôi, Qdrant hoạt động ra sao?",
    "Tài liệu của tôi sử dụng Qdrant như thế nào?",
    "Tìm phần nói về Qdrant trong tài liệu.",
    "Trong note của tôi, Qdrant có vai trò gì?",
    "Theo tài liệu đã lưu, Qdrant được dùng trong RAG như thế nào?",

    # ============================================================
    # RAG
    # ============================================================

    "Trong tài liệu của tôi, RAG được giải thích như thế nào?",
    "Theo note của tôi, RAG hoạt động ra sao?",
    "Tài liệu của tôi nói gì về RAG?",
    "Tìm trong tài liệu của tôi phần nói về RAG.",
    "Trong tài liệu tôi upload, RAG pipeline gồm những bước nào?",
    "Theo các note của tôi, RAG khác fine-tuning như thế nào?",
    "Tài liệu của tôi giải thích RAG như thế nào?",
    "Trong note của tôi, RAG được sử dụng vào mục đích gì?",
    "Tìm thông tin về RAG trong tài liệu của tôi.",
    "Theo tài liệu đã lưu, RAG có vai trò gì?",

    # ============================================================
    # EMBEDDING
    # ============================================================

    "Trong tài liệu của tôi, embedding được định nghĩa như thế nào?",
    "Theo note của tôi, embedding hoạt động ra sao?",
    "Tài liệu của tôi nói gì về embedding?",
    "Tìm trong tài liệu của tôi phần nói về embedding.",
    "Trong tài liệu tôi upload, embedding được sử dụng như thế nào?",
    "Theo các note của tôi, embedding model làm gì?",
    "Tài liệu của tôi giải thích text embedding như thế nào?",
    "Trong note của tôi, embedding có vai trò gì?",
    "Tìm thông tin về embedding trong tài liệu đã lưu.",
    "Theo tài liệu của tôi, embedding được tạo như thế nào?",

    # ============================================================
    # VECTOR DATABASE
    # ============================================================

    "Trong tài liệu của tôi, vector database được giải thích như thế nào?",
    "Theo note của tôi, vector database hoạt động ra sao?",
    "Tài liệu của tôi nói gì về vector database?",
    "Tìm trong tài liệu của tôi phần nói về vector database.",
    "Trong tài liệu tôi upload, vector database được sử dụng như thế nào?",
    "Theo các note của tôi, vector database có vai trò gì?",
    "Tài liệu của tôi giải thích cách lưu vector như thế nào?",
    "Tìm thông tin về vector database trong các note của tôi.",

    # ============================================================
    # MACHINE LEARNING
    # ============================================================

    "Trong tài liệu của tôi, Machine Learning được giải thích như thế nào?",
    "Theo note của tôi, Machine Learning hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Machine Learning?",
    "Tìm trong tài liệu của tôi phần nói về Machine Learning.",
    "Trong tài liệu tôi upload, Machine Learning được sử dụng như thế nào?",
    "Theo các note của tôi, Machine Learning có những loại nào?",
    "Tài liệu của tôi giải thích classification như thế nào?",
    "Tìm thông tin về supervised learning trong tài liệu của tôi.",
    "Trong note của tôi, regression được giải thích ra sao?",

    # ============================================================
    # LOGISTIC REGRESSION
    # ============================================================

    "Trong tài liệu của tôi, Logistic Regression được giải thích như thế nào?",
    "Theo note của tôi, Logistic Regression được sử dụng ra sao?",
    "Tài liệu của tôi nói gì về Logistic Regression?",
    "Tìm trong tài liệu của tôi phần nói về Logistic Regression.",
    "Trong tài liệu tôi upload, Logistic Regression được dùng để làm gì?",
    "Theo các note của tôi, Logistic Regression hoạt động như thế nào?",

    # ============================================================
    # ALGORITHMS
    # ============================================================

    "Trong tài liệu của tôi, Binary Search được giải thích như thế nào?",
    "Theo note của tôi, Binary Search hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Binary Search?",
    "Tìm trong tài liệu của tôi phần nói về Binary Search.",
    "Theo tài liệu của tôi, độ phức tạp của Binary Search là bao nhiêu?",

    "Trong tài liệu của tôi, BFS được giải thích như thế nào?",
    "Theo note của tôi, BFS được cài đặt ra sao?",
    "Tài liệu của tôi nói gì về BFS?",
    "Tìm trong tài liệu của tôi phần nói về BFS.",

    "Trong tài liệu của tôi, DFS được giải thích như thế nào?",
    "Theo note của tôi, DFS được cài đặt ra sao?",
    "Tài liệu của tôi nói gì về DFS?",
    "Tìm trong tài liệu của tôi phần nói về DFS.",

    "Trong tài liệu của tôi, Dijkstra được giải thích như thế nào?",
    "Theo note của tôi, Dijkstra hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Dijkstra?",
    "Tìm trong tài liệu của tôi phần nói về Dijkstra.",
    "Theo tài liệu của tôi, độ phức tạp của Dijkstra là bao nhiêu?",

    "Trong tài liệu của tôi, Quick Sort được giải thích như thế nào?",
    "Theo note của tôi, Quick Sort hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Quick Sort?",
    "Tìm trong tài liệu của tôi phần nói về Quick Sort.",

    "Trong tài liệu của tôi, Merge Sort được giải thích như thế nào?",
    "Theo note của tôi, Merge Sort hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Merge Sort?",
    "Tìm trong tài liệu của tôi phần nói về Merge Sort.",

    # ============================================================
    # DATA STRUCTURES
    # ============================================================

    "Trong tài liệu của tôi, Stack được giải thích như thế nào?",
    "Theo note của tôi, Stack hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Stack?",
    "Tìm trong tài liệu của tôi phần nói về Stack.",

    "Trong tài liệu của tôi, Queue được giải thích như thế nào?",
    "Theo note của tôi, Queue hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Queue?",
    "Tìm trong tài liệu của tôi phần nói về Queue.",

    "Trong tài liệu của tôi, Linked List được giải thích như thế nào?",
    "Theo note của tôi, Linked List hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Linked List?",
    "Tìm trong tài liệu của tôi phần nói về Linked List.",

    "Trong tài liệu của tôi, Hash Table được giải thích như thế nào?",
    "Theo note của tôi, Hash Table hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Hash Table?",
    "Tìm trong tài liệu của tôi phần nói về Hash Table.",

    "Trong tài liệu của tôi, BST được giải thích như thế nào?",
    "Theo note của tôi, Binary Search Tree hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Binary Search Tree?",
    "Tìm trong tài liệu của tôi phần nói về BST.",

    "Trong tài liệu của tôi, AVL Tree được giải thích như thế nào?",
    "Theo note của tôi, AVL Tree được cân bằng ra sao?",
    "Tài liệu của tôi nói gì về AVL Tree?",
    "Tìm trong tài liệu của tôi phần nói về AVL Tree.",

    # ============================================================
    # DATABASE / SQL
    # ============================================================

    "Trong tài liệu của tôi, SQL được giải thích như thế nào?",
    "Theo note của tôi, SQL được sử dụng ra sao?",
    "Tài liệu của tôi nói gì về SQL?",
    "Tìm trong tài liệu của tôi phần nói về SQL.",

    "Trong tài liệu của tôi, database được giải thích như thế nào?",
    "Theo note của tôi, database hoạt động ra sao?",
    "Tài liệu của tôi nói gì về database?",
    "Tìm trong tài liệu của tôi phần nói về database.",

    "Trong tài liệu của tôi, normalization được giải thích như thế nào?",
    "Theo note của tôi, normalization hoạt động ra sao?",
    "Tài liệu của tôi nói gì về normalization?",
    "Tìm trong tài liệu của tôi phần nói về normalization.",

    "Trong tài liệu của tôi, JOIN được giải thích như thế nào?",
    "Theo note của tôi, JOIN được sử dụng ra sao?",
    "Tài liệu của tôi nói gì về JOIN?",
    "Tìm trong tài liệu của tôi phần nói về JOIN.",

    # ============================================================
    # DOCKER
    # ============================================================

    "Trong tài liệu của tôi, Docker được giải thích như thế nào?",
    "Theo note của tôi, Docker được sử dụng ra sao?",
    "Tài liệu của tôi nói gì về Docker?",
    "Tìm trong tài liệu của tôi phần nói về Docker.",
    "Trong tài liệu tôi upload, Docker container được giải thích như thế nào?",
    "Theo tài liệu của tôi, Docker được cấu hình ra sao?",
    "Note của tôi nói gì về Docker image?",

    # ============================================================
    # GIT
    # ============================================================

    "Trong tài liệu của tôi, Git được giải thích như thế nào?",
    "Theo note của tôi, Git được sử dụng ra sao?",
    "Tài liệu của tôi nói gì về Git?",
    "Tìm trong tài liệu của tôi phần nói về Git.",
    "Trong note của tôi, Git merge được giải thích như thế nào?",
    "Theo tài liệu của tôi, Git branch hoạt động ra sao?",
    "Tài liệu của tôi nói gì về Git pull?",
]