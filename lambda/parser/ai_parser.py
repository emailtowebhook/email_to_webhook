import os
import json
from google import genai
from google.genai import types
from typing import Dict, Any, Optional
import traceback

# Try importing Daytona, handle if not installed/configured to avoid crash on load
try:
    from daytona_sdk import Daytona, Sandbox
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
            # Initialize Daytona
            daytona = Daytona(api_key=self.daytona_api_key)
            
            # Create a sandbox
            # Note: Creating a sandbox might take time.
            sandbox = daytona.create()
            
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
            # We use automatic function calling handling provided by newer SDKs or manually loop.
            # Given the strict JSON requirement for the final output, we might need a two-step process
            # OR allow the model to use the tool and then format the final answer as JSON.
            
            # Using generate_content with tools and automatic_function_calling
            # Note: response_mime_type='application/json' might conflict with tool calls 
            # if the model tries to call a tool first. 
            # We'll try to let it use tools, then ensure the final response is JSON.
            
            # Configuration for the chat/generation
            config = {
                "tools": tools,
                "response_mime_type": "application/json" # Request JSON for the FINAL response
            }
            
            # Note: In google-genai, automatic function calling might need explicit enablement
            # or we just pass the tools.
            # If we pass `response_mime_type`, the model is forced to output JSON.
            # It might not be able to emit a tool call (which is a structured proto message) 
            # if it's forced to emit JSON *text*.
            
            # STRATEGY: 
            # 1. Call without JSON constraint first, allowing tools.
            # 2. If it calls a tool, execute and feed back.
            # 3. Finally, ask for JSON format.
            
            # However, for simplicity and since 'parse_email' is primarily about extraction:
            # If the user explicitly wants to use tools, they usually provide a prompt that requires it.
            # For the default case, we might just keep it simple.
            # But the user asked to "add the option".
            
            # Let's try enabling tools but NOT forcing JSON initially if we want to allow tool use.
            # BUT the return type of this function expects Dict (JSON).
            
            # We will use a Chat session to handle the turn-taking if a tool is called.
            chat = self.client.chats.create(model=self.model_name, config={"tools": tools})
            
            response = chat.send_message(full_prompt)
            
            # Handle potential function calls (SDK might auto-handle if configured, 
            # but let's inspect response)
            # In google-genai, if we use `generate_content` it returns a response. 
            # If it has function calls, we need to execute them.
            # There isn't a built-in "auto-loop" in the low-level client usually unless using high-level abstraction.
            
            # Let's assume for now we just want to expose the tool.
            # If we want to enforce JSON output *after* tool use, we might need a specific instruction.
            
            # Simplified approach: Just expose the tool. If the model uses it, great.
            # But we need to ensure the *final* output is JSON.
            
            # If we force `response_mime_type="application/json"`, the model effectively *cannot* call tools
            # because the output format is constrained to JSON text, not FunctionCall objects.
            # So we must NOT set response_mime_type if we expect tool calls.
            
            # However, our return type requires parsing JSON.
            # So we might need to append "Return your final answer as a valid JSON object..." to the prompt.
            
            # Let's update the config to NOT force JSON, but add instructions.
            
            # Recalibrate:
            # If the user just wants the *option*, maybe we default to JSON extraction (no tools)
            # unless a specific flag is passed?
            # Or we try to be smart.
            
            # Given the user's prompt "add the option to run code as tool", 
            # I'll implement the tool method and register it. 
            # For the `parse_email` flow, to avoid breaking the strict JSON contract expected by the webhook caller,
            # I will stick to the original behavior (JSON constraint) by default.
            # But I'll add a new method `analyze_with_tools` or similar, OR just expose it and handle the loop.
            
            # Let's stick to `parse_email` but modify logic:
            # If tools are enabled (maybe via check or always), we assume a chat loop.
            
            # Actually, let's just add the tool to the `tools` list and see if Gemini 3 can handle 
            # "Call tool then output JSON". 
            # With `response_mime_type="application/json"`, it's risky.
            
            # I will leave the default `parse_email` as is (robust JSON extraction).
            # I will add `run_python_code` method to the class.
            # I will add logic to `parse_email`: IF `enable_tools` is True (argument), handle tool loop.
            # Since I can't change the signature easily without breaking callers (though I control the caller),
            # I'll default `enable_tools=False`?
            # The user said "add the option".
            
            # Updated implementation below:
            
            # For this turn, I will just implement the basic extraction with JSON enforcement 
            # BUT add the tool method to the class so it is available. 
            # If the user *wants* to use it, they can change the prompt/logic.
            # Wait, the user said "add the option... i will provide the api".
            # I should probably enable it if the API key is present.
            
            run_tools = bool(self.daytona_api_key)
            
            if run_tools:
                 # Use chat to handle potential tool loops
                 # Manual loop for tool execution
                 
                 chat = self.client.chats.create(
                    model=self.model_name,
                    config={"tools": tools} 
                 )
                 
                 response = chat.send_message(full_prompt)
                 
                 # Simple loop for function calls
                 # Note: This is a basic implementation. 
                 # Real-world usage might need depth limits, etc.
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
                 # Now we need to ensure it's JSON. 
                 # If the model returned text that isn't JSON, we might need to ask it to format it.
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
