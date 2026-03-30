import ollama
from groq import Groq
from pydantic import BaseModel
from typing import Optional, List
import abc
import dotenv
dotenv.load_dotenv()
class NotificationCategory(BaseModel):
    is_job_or_event: bool
    title: str
    date: Optional[str]
    time: Optional[str]
    urgency_score: int
    short_summary: str

class YTTask(BaseModel):
    task: str
    priority: str
    description: str

class YTTaskList(BaseModel):
    video_id: str
    tasks: List[YTTask]

class BaseAIEngine(abc.ABC):
    def __init__(self, config_data):
        self.config_data = config_data

    def _get_final_prompt(self):
        base_prompt = self.config_data.get("system_prompt", "")
        importance = self.config_data.get("importance_keywords", "")
        ignore = self.config_data.get("ignore_keywords", "")
        
        rules = f"\n\nAdditional Importance Rules:\n- Treat these as very important (HIGH SCORE): {importance}"
        rules += f"\n- Treat these as NOT important (LOW SCORE): {ignore}"
        
        return base_prompt + rules

    @abc.abstractmethod
    def categorize_message(self, text: str) -> Optional[NotificationCategory]:
        pass

    @abc.abstractmethod
    def generate_tasks_from_transcript(self, video_id: str, text: str) -> Optional[YTTaskList]:
        pass

class OllamaEngine(BaseAIEngine):
    def __init__(self, config_data):
        super().__init__(config_data)
        self.model_name = config_data["ollama_model"]

    def categorize_message(self, text: str) -> Optional[NotificationCategory]:
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {
                        'role': 'system', 
                        'content': self._get_final_prompt()
                    },
                    {'role': 'user', 'content': text}
                ],
                format=NotificationCategory.model_json_schema()
            )
            return NotificationCategory.model_validate_json(response.message.content)
        except Exception as e:
            print(f"❌ Ollama Error: {e}")
            return None

    def generate_tasks_from_transcript(self, video_id: str, text: str) -> Optional[YTTaskList]:
        try:
            system_prompt = "You are an assistant that extracts a list of actionable tasks or key takeaways from a YouTube video transcript. Return a JSON object with a 'video_id' and a 'tasks' list containing 'task', 'priority', and 'description'."
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"Transcript for {video_id}:\n{text}"}
                ],
                format=YTTaskList.model_json_schema()
            )
            return YTTaskList.model_validate_json(response.message.content)
        except Exception as e:
            print(f"❌ Ollama Error generating tasks: {e}")
            return None

class GroqEngine(BaseAIEngine):
    def __init__(self, config_data):
        super().__init__(config_data)
        self.client = Groq(api_key=config_data["groq_api_key"])
        self.model_name = config_data["groq_model"]

    def categorize_message(self, text: str) -> Optional[NotificationCategory]:
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": self._get_final_prompt() + "\nReturn ONLY valid JSON."
                    },
                    {
                        "role": "user",
                        "content": text,
                    }
                ],
                model=self.model_name,
                response_format={"type": "json_object"}
            )
            return NotificationCategory.model_validate_json(chat_completion.choices[0].message.content)
        except Exception as e:
            print(f"❌ Groq Error: {e}")
            return None

    def generate_tasks_from_transcript(self, video_id: str, text: str) -> Optional[YTTaskList]:
        try:
            system_prompt = "You are an assistant that extracts a list of actionable tasks or key takeaways from a YouTube video transcript. Return a JSON object with a 'video_id' and a 'tasks' list containing 'task', 'priority', and 'description'. Return ONLY valid JSON."
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Transcript for {video_id}:\n{text}"}
                ],
                model=self.model_name,
                response_format={"type": "json_object"}
            )
            return YTTaskList.model_validate_json(chat_completion.choices[0].message.content)
        except Exception as e:
            print(f"❌ Groq Error generating tasks: {e}")
            return None

def get_engine(config_data):
    if config_data["provider"] == "groq":
        return GroqEngine(config_data)
    else:
        return OllamaEngine(config_data)

def list_ollama_models() -> List[str]:
    try:
        response = ollama.list()
        # In newer versions, response.models is a list of Model objects
        # and the attribute is .model or .name
        return [m.model for m in response.models]
    except Exception as e:
        print(f"⚠️ Error listing Ollama models: {e}")
        return []

def list_groq_models(api_key: str = None) -> List[str]:
    # Common Groq models if API fails or key missing
    default_groq = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"]
    if not api_key:
        return default_groq
    try:
        client = Groq(api_key=api_key)
        models = client.models.list()
        return [m.id for m in models.data]
    except Exception as e:
        print(f"⚠️ Error listing Groq models: {e}")
        return default_groq

import json
def save_tasks_to_json(tasks: YTTaskList, filename: str):
    with open(filename, 'w') as f:
        json.dump(tasks.model_dump(), f, indent=4)
    print(f"✅ Saved tasks to {filename}")


if __name__ == "__main__":
    import os
    
    # 1. Configuration
    groq_model = "llama-3.1-8b-instant"
    ollama_model = "qwen2.5:3b"
    prompt = "Write a short 1-sentence tagline for an AI assistant."
    
    # Try Groq First
    api_key = os.environ.get("GROQ_API_KEY")
    
    if api_key:
        try:
            print(f"🚀 Attempting Groq ({groq_model})...")
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                max_completion_tokens=1024,
                top_p=1,
                stream=True,
            )

            print("--- Groq Streaming Output ---")
            for chunk in completion:
                content = chunk.choices[0].delta.content
                if content:
                    print(content, end="", flush=True)
            print("\n--- Stream Complete ---\n")
            exit(0) # Success, exit
        except Exception as e:
            print(f"❌ Groq failed: {e}")
    else:
        print("💡 No GROQ_API_KEY found.")

    # 2. Fallback to Ollama
    print(f"🔄 Falling back to Ollama ({ollama_model})...")
    try:
        # Note: ollama.chat doesn't natively return a generator like Groq's SDK unless specified
        # but the 'ollama' python library supports streaming if 'stream=True' is passed.
        response = ollama.chat(
            model=ollama_model,
            messages=[{'role': 'user', 'content': prompt}],
            stream=True,
        )

        print(f"--- Ollama ({ollama_model}) Streaming Output ---")
        for chunk in response:
            print(chunk['message']['content'], end='', flush=True)
        print("\n--- Stream Complete ---")
    except Exception as e:
        print(f"❌ Ollama also failed: {e}")
        print("⚠️ Ensure Ollama is running (`ollama serve`) and the model is pulled.")

