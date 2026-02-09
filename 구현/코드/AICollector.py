from pathlib import Path

def collect_py_files(output_txt: str = "result.txt"):
    base_path = Path(__file__).parent
    py_files = list(base_path.rglob("*.py"))

    def sort_key(path: Path):
        name = path.name.lower()
        if name == "__init__.py":
            return (0, str(path))
        if name == "main.py":
            return (1, str(path))
        return (2, str(path))

    py_files.sort(key=sort_key)

    with open(output_txt, "w", encoding="utf-8") as out:
        for py_file in py_files:
            relative_path = py_file.relative_to(base_path)

            out.write("=" * 80 + "\n")
            out.write(f"FILE: {relative_path}\n")
            out.write("=" * 80 + "\n")

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f, start=1):
                        out.write(f"{idx:4d}: {line}")
            except Exception as e:
                out.write(f"[ERROR] 파일을 읽을 수 없습니다: {e}\n")

            out.write("\n\n")


if __name__ == "__main__":
    collect_py_files()
