import os
import json
from google import genai
from typing import Dict, Any

class AIParser:
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY')
        # Default to Gemini 3 (preview) as requested, fallback to 1.5 if needed
        self.model_name = os.environ.get('GEMINI_MODEL', 'gemini-3-pro-preview')
        
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            print("Warning: GEMINI_API_KEY not set")

    def parse_email(self, email_data: Dict[str, Any], prompt: str = None) -> Dict[str, Any]:
        """
        Send email data to Gemini to extract structured information.
        """
        if not self.api_key:
            print("Skipping AI parsing: No API key")
            return {}

        if not prompt:
            prompt = """
            Analyze the following email data and extract key entities and intent.
            Return a JSON object with the following schema:
            {
                "summary": "Brief summary of the email",
                "intent": "The primary intent of the sender (e.g., 'inquiry', 'complaint', 'purchase')",
                "sentiment": "sentiment analysis (positive, neutral, negative)",
                "key_entities": ["list of extracted entities like names, companies, dates"],
                "action_items": ["list of suggested actions"]
            }
            """

        # prepare content
        # We focus on body, subject, sender, recipient for the AI analysis
        relevant_data = {
            "subject": email_data.get("subject"),
            "sender": email_data.get("sender"),
            "recipient": email_data.get("recipient"),
            "date": email_data.get("date"),
            "body": email_data.get("body") or email_data.get("html_body", "")[:5000] # truncate if too long/only html
        }

        full_prompt = f"""
        {prompt}

        Email Data:
        {json.dumps(relevant_data, default=str)}
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config={
                    "response_mime_type": "application/json"
                }
            )
            
            # Parse the response text as JSON
            return json.loads(response.text)
            
        except Exception as e:
            print(f"Error during AI parsing: {e}")
            return {"error": str(e)}

