from BackEnd.app.query_router.router import QueryRouter


def main():

    router = QueryRouter(
        threshold=0.85
    )

    queries = [
        "Python là gì?",
        "Qdrant dùng để làm gì?",
        "Trong tài liệu của tôi, Qdrant được giải thích như thế nào?",
        "Trong note DSA của tôi, AVL Tree hoạt động thế nào?",
        "2 cộng 2 bằng bao nhiêu?",
        "Tài liệu của tôi nói gì về RAG?",
        "FastAPI là gì?",
        "Trong tài liệu của tôi FastAPI được cấu hình như thế nào?",
    ]

    for query in queries:

        result = router.route(query)

        print()
        print("=" * 60)

        print(
            "Query:",
            query
        )

        print(
            "Route:",
            result["route"]
        )

        print(
            "Confidence:",
            f"{result['confidence']:.4f}"
        )


if __name__ == "__main__":
    main()