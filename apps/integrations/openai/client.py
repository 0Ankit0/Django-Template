from openai import OpenAI, APIError
from config import settings
from .exceptions import OpenAIClientException
from pydantic import BaseModel

class IdeasResponse(BaseModel):
    ideas: list[str]

OPEN_AI_API_ERROR_MSG = "OpenAI service is currently unavailable. Please try again in a couple seconds."

class OpenAIClient:
    @staticmethod
    def get_saas_ideas(keywords: list[str]) -> IdeasResponse:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = f"Get me 3-5 {', '.join(keywords)} saas ideas. Return them as a simple bulleted list."

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates SaaS ideas."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            # Simple parsing: split by newlines, remove "-" or numbers
            ideas = []
            if content:
                lines = content.split('\n')
                for line in lines:
                    cleaned = line.strip().lstrip('-').lstrip('1234567890.').strip()
                    if cleaned:
                        ideas.append(cleaned)

            return IdeasResponse(ideas=ideas)
            
        except APIError as error:
            raise OpenAIClientException(OPEN_AI_API_ERROR_MSG) from error
        except Exception as error:
             raise OpenAIClientException(f"An error occurred: {str(error)}") from error
