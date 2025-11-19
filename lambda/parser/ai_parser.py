import os
import json
from google import genai
from google.genai import types
from typing import Dict, Any, Optional
import traceback

# Try importing Daytona, handle if not installed/configured to avoid crash on load
try:
    from daytona_sdk import DaytonaConfig, Daytona, CreateSandboxFromSnapshotParams
    DAYTONA_AVAILABLE = True
except ImportError:
    DAYTONA_AVAILABLE = False
    print("Daytona SDK not available")

class AIParser:
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY')
        self.daytona_api_key = os.environ.get('DAYTONA_API_KEY')
        # Default to Gemini 3 (preview) as requested, fallback to 1.5 if needed
        self.model_name = os.environ.get('GEMINI_MODEL', 'gemini-3-pro-preview')
        
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            print("Warning: GEMINI_API_KEY not set")

    def run_python_code(self, code: str) -> str:
        """
        Executes Python code in a Daytona sandbox and returns the output.
        """
        if not DAYTONA_AVAILABLE:
            return "Daytona SDK not installed."
        if not self.daytona_api_key:
            return "DAYTONA_API_KEY not set."

        print(f"Executing code in Daytona:\n{code}")
        try:
            config = DaytonaConfig(api_key=self.daytona_api_key)

            # Initialize Daytona
            # Define the configuration
            daytona = Daytona(config=config)
            
            # Create a sandbox
            # Note: Creating a sandbox might take time.
            params = CreateSandboxFromSnapshotParams(
            ephemeral=True,
            auto_stop_interval=1 # the ephemeral sandbox will be deleted after 5 minutes of inactivity
            )
            sandbox = daytona.create(params)
            
            try:
                # Execute code
                execution = sandbox.process.code_run(code)
                
                output = ""
                if execution.result:
                    output += f"Result: {execution.result}\n"
                
                if execution.exit_code != 0:
                    output += f"Exit Code: {execution.exit_code}\n"
                
                # We could handle artifacts/charts here if needed, 
                # for now just return text output.
                return output.strip()
            finally:
                if sandbox:
                    sandbox.delete()
                # Cleanup: Although the Python SDK might not expose destroy on sandbox object directly 
                # depending on version, typically we should try to cleanup if possible.
                # If the SDK manages lifecycle or if we are in a short-lived lambda, 
                # we might leave it to the platform or timeout. 
                # Checking SDK reference: usually sandbox.delete() or daytona.remove(sandbox)
                # For now, assuming standard usage as per docs which didn't emphasize cleanup in snippets.
                pass 

        except Exception as e:
            print(f"Error executing code in Daytona: {e}")
            return f"Error: {str(e)}"

    def parse_email(self, email_data: Dict[str, Any], prompt: str = None) -> Dict[str, Any]:
        """
        Send email data to Gemini to extract structured information.
        Optionally uses tools if the prompt implies complex analysis.
        """
        if not self.api_key:
            print("Skipping AI parsing: No API key")
            return {}

        if not prompt:
            prompt = """
            Analyze the following email data and extract key entities and intent.
            Return a JSON object with the following schema:
            {
                "is_image_contain_a_cat": "boolean",
                "summary": "Brief summary of the email",
                "intent": "The primary intent of the sender (e.g., 'inquiry', 'complaint', 'purchase')",
                "sentiment": "sentiment analysis (positive, neutral, negative)",
                "key_entities": ["list of extracted entities like names, companies, dates"],
                "action_items": ["list of suggested actions"]
            }
            """

        # prepare content
        relevant_data = {
            "subject": email_data.get("subject"),
            "sender": email_data.get("sender"),
            "recipient": email_data.get("recipient"),
            "date": email_data.get("date"),
            "body": email_data.get("body") or email_data.get("html_body", "")[:5000] 
        }

        full_prompt = f"""
        {prompt}

        Email Data:
        {json.dumps(relevant_data, default=str)}
        """

        # Define tools
        # We expose the tool to the model
        tools = [self.run_python_code]

        try:
            run_tools = bool(self.daytona_api_key)
            
            if run_tools:
                 # Use chat to handle potential tool loops
                 chat = self.client.chats.create(
                    model=self.model_name,
                    config={"tools": tools} 
                 )
                 
                 response = chat.send_message(full_prompt)
                 
                 # Simple loop for function calls
                 while response.function_calls:
                    for call in response.function_calls:
                        if call.name == "run_python_code":
                            code_arg = call.args.get("code")
                            tool_result = self.run_python_code(code_arg)
                            # Send result back
                            response = chat.send_message(
                                types.Part.from_function_response(
                                    name="run_python_code",
                                    response={"result": tool_result}
                                )
                            )
            
                 # After tool loop (or if no tools called), get the final text.
                 final_text = response.text
                 
                 # Try to parse
                 try:
                     # Strip markdown code blocks if present
                     clean_text = final_text.strip()
                     if clean_text.startswith("```json"):
                         clean_text = clean_text[7:]
                     if clean_text.endswith("```"):
                         clean_text = clean_text[:-3]
                     return json.loads(clean_text)
                 except json.JSONDecodeError:
                     # Fallback: Ask model to format as JSON
                     json_response = chat.send_message(
                         "Format the previous analysis as a valid JSON object matching the requested schema."
                     )
                     clean_text = json_response.text.strip()
                     if clean_text.startswith("```json"):
                         clean_text = clean_text[7:]
                     if clean_text.endswith("```"):
                         clean_text = clean_text[:-3]
                     return json.loads(clean_text)
                     
            else:
                # Original extraction flow (fast, forced JSON)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config={
                        "response_mime_type": "application/json"
                    }
                )
                return json.loads(response.text)
            
        except Exception as e:
            print(f"Error during AI parsing: {traceback.format_exc()}")
            return {"error": str(e)}
