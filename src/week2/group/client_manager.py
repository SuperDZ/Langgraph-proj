from  openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file

client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")