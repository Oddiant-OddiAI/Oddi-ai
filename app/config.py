from openai import OpenAI
from groq import Groq
from mistralai.client import Mistral
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

mistral_client = Mistral(
    api_key=os.getenv("MISTRAL_API_KEY")
)