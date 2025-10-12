#!/usr/bin/env python3
"""
Training Session Manager
Manages training sessions with Ollama API
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional
import logging

class TrainingSessionManager:
    """Manage training sessions with Ollama"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.session = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def check_ollama_running(self) -> bool:
        """Check if Ollama is running"""
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                return response.status == 200
        except Exception as e:
            self.logger.error(f"Ollama not accessible: {e}")
            return False

    async def generate_completion(self, model: str, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Generate completion using Ollama API"""
        url = f"{self.base_url}/api/generate"

        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.3),
                "num_predict": kwargs.get("max_tokens", 4096),
                "num_ctx": kwargs.get("context_length", 4096)
            }
        }

        if system_prompt:
            data["system"] = system_prompt

        try:
            async with self.session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status == 200:
                    result = await response.json()
                    return {
                        "success": True,
                        "response": result.get("response", ""),
                        "model": model,
                        "total_duration": result.get("total_duration", 0),
                        "load_duration": result.get("load_duration", 0),
                        "prompt_eval_count": result.get("prompt_eval_count", 0),
                        "eval_count": result.get("eval_count", 0)
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"API error {response.status}: {error_text}"
                    }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Request timed out after 300 seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }

    async def train_with_example(self, model: str, example: Dict[str, Any]) -> Dict[str, Any]:
        """Train model with a single example"""
        # Convert conversation to training prompt
        prompt = self._format_conversation_for_training(example["conversation"])

        # Create system prompt that emphasizes tool usage
        system_prompt = """You are an AI assistant that uses tools to help users.

CRITICAL RULES FOR TOOL CALLS:
1. Always use JSON format: {"type":"tool_call","name":"TOOL_NAME","args":{...}}
2. Use correct parameter names (e.g., "file_path" not "path")
3. Wait for tool results before responding to user
4. If file_search or directory_list is used, you'll get auto-chained results automatically
5. Handle errors gracefully and suggest alternatives

Available tools: file_read, file_write, file_edit, file_search, file_delete, directory_list, grep_search, bash_execute, git_operations, system_info, process_manage, web_search, web_fetch, code_analyze, change_directory"""

        try:
            result = await self.generate_completion(
                model=model,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,  # Low temperature for consistent tool calling
                max_tokens=2048
            )

            if result["success"]:
                # Validate that model produced correct tool call format
                response_text = result["response"]
                is_valid = self._validate_tool_response(response_text, example)

                return {
                    "success": True,
                    "valid_format": is_valid,
                    "response": response_text,
                    "example_id": example.get("scenario", "unknown"),
                    "metrics": {
                        "total_duration_ms": result.get("total_duration", 0) / 1_000_000,
                        "tokens_generated": result.get("eval_count", 0)
                    }
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "example_id": example.get("scenario", "unknown")
                }

        except Exception as e:
            self.logger.error(f"Training failed for example: {e}")
            return {
                "success": False,
                "error": str(e),
                "example_id": example.get("scenario", "unknown")
            }

    def _format_conversation_for_training(self, conversation: List[Dict[str, str]]) -> str:
        """Format conversation for training prompt"""
        prompt_parts = []

        for turn in conversation:
            role = turn.get("role", "")
            content = turn.get("content", "")

            if role == "system":
                # System messages become tool responses
                prompt_parts.append(f"[TOOL RESPONSE]\n{content}\n")
            elif role == "user":
                prompt_parts.append(f"[USER]\n{content}\n")
            elif role == "assistant":
                if "tool_call" in content:
                    # Extract and format tool call
                    try:
                        tool_data = json.loads(content)
                        prompt_parts.append(f"[ASSISTANT - TOOL CALL]\n{json.dumps(tool_data, indent=2)}\n")
                    except:
                        prompt_parts.append(f"[ASSISTANT - TOOL CALL]\n{content}\n")
                else:
                    prompt_parts.append(f"[ASSISTANT]\n{content}\n")

        return "\n".join(prompt_parts)

    def _validate_tool_response(self, response: str, example: Dict[str, Any]) -> bool:
        """Validate that response contains proper tool call format"""
        # Check for JSON structure
        if '{"type":"tool_call"' not in response:
            return False

        # Check for required fields
        if '"name":' not in response or '"args":' not in response:
            return False

        # Try to parse as JSON
        try:
            # Extract JSON from response
            start = response.find('{"type":"tool_call"')
            if start == -1:
                return False

            end = response.find('}', start)
            bracket_count = 1
            pos = start + 1

            while bracket_count > 0 and pos < len(response):
                if response[pos] == '{':
                    bracket_count += 1
                elif response[pos] == '}':
                    bracket_count -= 1
                pos += 1

            json_str = response[start:pos]
            parsed = json.loads(json_str)

            # Validate structure
            if parsed.get("type") != "tool_call":
                return False
            if "name" not in parsed or "args" not in parsed:
                return False

            return True

        except json.JSONDecodeError:
            return False

    async def evaluate_model(self, model: str, test_examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate model performance on test examples"""
        results = {
            "total": len(test_examples),
            "passed": 0,
            "failed": 0,
            "invalid_format": 0,
            "avg_response_time_ms": 0,
            "examples": []
        }

        total_time = 0

        for example in test_examples:
            result = await self.train_with_example(model, example)

            example_result = {
                "scenario": example.get("scenario", "unknown"),
                "success": result.get("success", False),
                "valid_format": result.get("valid_format", False)
            }

            if result.get("success"):
                if result.get("valid_format"):
                    results["passed"] += 1
                else:
                    results["invalid_format"] += 1

                total_time += result.get("metrics", {}).get("total_duration_ms", 0)
            else:
                results["failed"] += 1
                example_result["error"] = result.get("error", "Unknown")

            results["examples"].append(example_result)

        if results["total"] > 0:
            results["avg_response_time_ms"] = total_time / results["total"]
            results["pass_rate"] = (results["passed"] / results["total"]) * 100

        return results

    async def load_model(self, model_name: str) -> bool:
        """Preload model into memory"""
        try:
            # Send a simple request to load the model
            result = await self.generate_completion(
                model=model_name,
                prompt="Hello",
                temperature=0.1,
                max_tokens=10
            )
            return result.get("success", False)
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            return False

    async def unload_model(self, model_name: str) -> bool:
        """Unload model from memory"""
        try:
            url = f"{self.base_url}/api/generate"
            data = {
                "model": model_name,
                "keep_alive": 0  # Unload immediately
            }
            async with self.session.post(url, json=data) as response:
                return response.status == 200
        except Exception as e:
            self.logger.error(f"Failed to unload model: {e}")
            return False
