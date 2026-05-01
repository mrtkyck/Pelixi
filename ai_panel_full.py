import sys
import base64
import zipfile
import tempfile
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
client = OpenAI()

MODEL = "gpt-5.4-mini"

TEXT_EXTS = [".py", ".txt", ".md", ".json", ".csv", ".html", ".css", ".js", ".ts", ".yml", ".yaml"]
IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp"]


def multiline_input(title="Komutu yaz"):
    print(f"\n{title}")
    print("Bitirmek için tek satıra END yaz.")
    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def read_project(folder, max_chars_per_file=4000, max_total_chars=70000):
    folder = Path(folder)
    chunks = []
    total = 0

    skip_dirs = {".venv", "venv", "__pycache__", ".git", "node_modules", "dist", "build"}

    for path in folder.rglob("*"):
        if any(part in skip_dirs for part in path.parts):
            continue

        if path.is_file() and path.suffix.lower() in TEXT_EXTS:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")[:max_chars_per_file]
                block = f"\n--- DOSYA: {path.relative_to(folder)} ---\n{content}\n"
                if total + len(block) > max_total_chars:
                    break
                chunks.append(block)
                total += len(block)
            except Exception:
                pass

    return "\n".join(chunks)


def analyze_project(folder, user_prompt):
    project_data = read_project(folder)

    full_prompt = f"""
Aşağıdaki projeyi uzman yazılımcı gibi incele.

Kullanıcının isteği:
{user_prompt}

Proje dosyaları:
{project_data}

Cevap verirken:
- Hangi dosyada ne değişecek açık yaz.
- Gerekli kod bloklarını dosya adıyla ver.
- Mevcut sistemi bozma.
- Türkçe anlat.
"""

    response = client.responses.create(
        model=MODEL,
        input=full_prompt
    )

    print("\n🤖 AI:\n")
    print(response.output_text)


def analyze_zip(zip_path, user_prompt):
    zip_path = Path(zip_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_dir)

        analyze_project(temp_dir, user_prompt)


def analyze_image(path, user_prompt):
    image_bytes = Path(path).read_bytes()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    ext = Path(path).suffix.lower().replace(".", "")
    mime = "jpeg" if ext == "jpg" else ext

    response = client.responses.create(
        model=MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {"type": "input_image", "image_url": f"data:image/{mime};base64,{b64}"}
                ]
            }
        ]
    )

    print("\n🤖 AI:\n")
    print(response.output_text)


print("🤖 FULL AI DEVELOPER PANEL V2")
print("Modlar: chat / project / zip / image / exit")

while True:
    mode = input("\nMod seç: ").strip().lower()

    if mode == "exit":
        print("👋 Çıkılıyor...")
        break

    elif mode == "chat":
        prompt = multiline_input("Sorunu yaz:")
        response = client.responses.create(
            model=MODEL,
            input=prompt
        )
        print("\n🤖 AI:\n")
        print(response.output_text)

    elif mode == "project":
        folder = input("Proje klasörü: ").strip().strip('"')
        prompt = multiline_input("Projeye ne yaptırmak istiyorsun?")
        analyze_project(folder, prompt)

    elif mode == "zip":
        zip_path = input("Zip dosya yolu: ").strip().strip('"')
        prompt = multiline_input("Zip içindeki projeye ne yaptırmak istiyorsun?")

        if not Path(zip_path).exists():
            print("❌ Zip dosyası bulunamadı.")
            continue

        analyze_zip(zip_path, prompt)

    elif mode == "image":
        path = input("Görsel yolu: ").strip().strip('"')
        prompt = multiline_input("Görsel için ne yapayım?")

        if not Path(path).exists():
            print("❌ Görsel bulunamadı.")
            continue

        analyze_image(path, prompt)

    else:
        print("❌ Geçersiz mod.")