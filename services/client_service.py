from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
import os
import json 
from typing import List

# Initialize client with your API key

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def paraphrase(self, text: str) -> List[str]:
        response = self.client.chat.completions.create(
            model="gpt-4o",  
            messages=[
                {"role": "system", "content": """
                Bạn là agent hiểu về cách parahrase và dịch sang tiếng anh đoạn text sau để clip, siglip2 và beit3 hiểu.
                Đảm bảo trả về dạng json như sau:
                {
                    "clip": "paraphrase đoạn text thành tiếng anh để clip hiểu",
                    "siglip2": "paraphrase đoạn text thành tiếng anh để siglip2 hiểu",
                    "beit3": "paraphrase đoạn text thành tiếng anh để beit3 hiểu"
                }
                """},
                {"role": "user", "content": f"TEXT: {text}"}
            ],
        )

        paraphrased = response.choices[0].message.content
        jsons = json.loads(paraphrased)

        return jsons.values()
    
    def question(self, text: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o",  
            messages=[
                {"role": "user", "content": text}
            ],
        )

        return response.choices[0].message.content

        
