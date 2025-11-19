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
        self.active_sandboxes = {}
        
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            print("Warning: GEMINI_API_KEY not set")

    def create_sandbox(self) -> str:
        """
        Creates a new Daytona sandbox and returns its ID.
        """
        if not DAYTONA_AVAILABLE:
            return "Daytona SDK not installed."
        if not self.daytona_api_key:
            return "DAYTONA_API_KEY not set."

        print("Creating Daytona sandbox...")
        try:
            config = DaytonaConfig(api_key=self.daytona_api_key)
            daytona = Daytona(config=config)
            
            # Create a sandbox
            params = CreateSandboxFromSnapshotParams(
                ephemeral=True,
                auto_stop_interval=1 # the ephemeral sandbox will be deleted after 5 minutes of inactivity
            )
            sandbox = daytona.create(params)
            self.active_sandboxes[sandbox.id] = sandbox
            print(f"Sandbox created: {sandbox.id}")
            return sandbox.id
        except Exception as e:
            print(f"Error creating sandbox: {e}")
            return f"Error creating sandbox: {str(e)}"

    def upload_file(self, sandbox_id: str, file_path: str, content: str) -> str:
        """
        Uploads a file to the specified sandbox.
        """
        sandbox = self.active_sandboxes.get(sandbox_id)
        if not sandbox:
            return f"Sandbox {sandbox_id} not found"
            
        print(f"Uploading file {file_path} to sandbox {sandbox_id}")
        try:
            # Use Daytona SDK's native upload functionality
            sandbox.fs.upload_file(file_path, content)
            return f"File uploaded successfully to {file_path}"
        except Exception as e:
            print(f"Error uploading file: {e}")
            return f"Error uploading file: {str(e)}"

    def run_code(self, sandbox_id: str, code: str) -> str:
        """
        Runs Python code in the specified sandbox.
        """
        sandbox = self.active_sandboxes.get(sandbox_id)
        if not sandbox:
            return f"Sandbox {sandbox_id} not found"
            
        print(f"Executing code in sandbox {sandbox_id}:\n{code}")
        try:
            execution = sandbox.process.code_run(code)
            
            output = ""
            if execution.result:
                output += f"Result: {execution.result}\n"
            
            if execution.exit_code != 0:
                output += f"Exit Code: {execution.exit_code}\n"
            
            return output.strip()
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
        tools = [self.create_sandbox, self.upload_file, self.run_code]

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
                        tool_name = call.name
                        args = call.args
                        
                        print(f"Tool call: {tool_name}")
                        tool_result = "Unknown tool"
                        
                        if tool_name == "create_sandbox":
                            tool_result = self.create_sandbox()
                        elif tool_name == "upload_file":
                            tool_result = self.upload_file(
                                args.get("sandbox_id"), 
                                args.get("file_path"), 
                                args.get("content")
                            )
                        elif tool_name == "run_code":
                            tool_result = self.run_code(
                                args.get("sandbox_id"), 
                                args.get("code")
                            )
                        
                        # Send result back
                        response = chat.send_message(
                            types.Part.from_function_response(
                                name=tool_name,
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
        finally:
            # Cleanup sandboxes
            if self.active_sandboxes:
                print(f"Cleaning up {len(self.active_sandboxes)} sandboxes...")
                for sid, sandbox in self.active_sandboxes.items():
                    try:
                        sandbox.delete()
                    except Exception as e:
                        print(f"Error deleting sandbox {sid}: {e}")
                self.active_sandboxes.clear()
