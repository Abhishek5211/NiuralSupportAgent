import os
import openai
from dotenv import load_dotenv

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.responses.create(
    model="gpt-5.6",
    input="Write a one-sentence bedtime story about a unicorn."
)
print(response.output_text)
