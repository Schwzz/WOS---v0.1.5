import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()


def chat(model, messages):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("WLLM: GEMINI_API_KEY was not found.")
        return None

    try:
        client = genai.Client(api_key=api_key)

        system_prompt = ""
        contents = []

        for message in messages:
            role = message["role"]
            content = message["content"]

            if role == "system":
                system_prompt = content
            elif role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=content)]
                    )
                )
            elif role == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part(text=content)]
                    )
                )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                )
            )
        )

        return response.text

    except Exception as e:
        print(f"WLLM: Gemini returned an error: {e}")
        return None