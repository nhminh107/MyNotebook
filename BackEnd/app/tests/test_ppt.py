from BackEnd.app.doc_extractor.extractor import ExtractorFactory


def main():

    file_path = r"D:\MyProject\MyNotebook\BackEnd\app\test.pptx"

    extractor = ExtractorFactory.create(file_path)

    result = extractor.extract(file_path)

    print("=" * 60)
    print("Number of pages/slides:", len(result))

    for item in result:

        print("\n" + "=" * 60)

        print("Page:", item.get("page"))

        print("OCR:", item.get("ocr_used"))

        print("Texts:")

        for text in item.get("texts", []):
            print(text[:1000])


if __name__ == "__main__":
    main()