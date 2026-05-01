import sys
from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
client = OpenAI()

response = client.responses.create(
    model="gpt-5.4-mini",
    input="Bana Türkçe kısa bir test cümlesi yaz."
)

print(response.output_text)