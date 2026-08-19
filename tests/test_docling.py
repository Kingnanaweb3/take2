from docling.document_converter import DocumentConverter

SAMPLE_PATH = "data/sample_scripts/sample.md"

def main():
    converter = DocumentConverter()
    result = converter.convert(SAMPLE_PATH)
    markdown = result.document.export_to_markdown()

    print("--- Parsed output (first 1000 chars) ---")
    print(markdown[:1000])
    print("\n--- Success: Docling parsed the file ---")

if __name__ == "__main__":
    main()