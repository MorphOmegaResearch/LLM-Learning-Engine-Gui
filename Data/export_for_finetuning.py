#!/usr/bin/env python3
"""
Export OpenCode training data for fine-tuning with Ollama and other tools
"""

import json
from pathlib import Path
from typing import List, Dict, Any

class TrainingDataExporter:
    """Export training data in various formats for fine-tuning"""

    def __init__(self, training_data: List[Dict[str, Any]], output_dir: str):
        self.training_data = training_data
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_for_ollama(self, model_name: str, base_model: str) -> str:
        """
        Export as Ollama Modelfile format for fine-tuning

        Usage:
            ollama create {model_name} -f {output_file}
        """
        modelfile_path = self.output_dir / f"Modelfile_{model_name}"

        # Create Modelfile header
        modelfile_content = [
            f"FROM {base_model}",
            "",
            "# OpenCode Tool Training System Prompt",
            'SYSTEM """You are an AI assistant that uses tools to help users.',
            "",
            "CRITICAL RULES FOR TOOL USAGE:",
            "1. Always use JSON format: {\"type\":\"tool_call\",\"name\":\"TOOL_NAME\",\"args\":{...}}",
            "2. Use correct parameter names:",
            "   - file_path (NOT path) for file operations",
            "   - pattern for search operations",
            "   - operation for git/process commands",
            "3. Wait for tool results before responding to the user",
            "4. Never hallucinate tool parameters - use only what's provided",
            "",
            "AVAILABLE TOOLS:",
            "- file_read: Read file contents",
            "  Args: {\"file_path\": \"path/to/file\"}",
            "",
            "- file_write: Create or overwrite file",
            "  Args: {\"file_path\": \"path/to/file\", \"content\": \"file contents\"}",
            "",
            "- file_edit: Find and replace text in file",
            "  Args: {\"file_path\": \"path/to/file\", \"old_text\": \"find this\", \"new_text\": \"replace with this\"}",
            "",
            "- file_delete: Delete a file",
            "  Args: {\"file_path\": \"path/to/file\"}",
            "",
            "- file_search: Find files matching pattern",
            "  Args: {\"pattern\": \"*.py\", \"path\": \".\"}",
            "",
            "- grep_search: Search for text in files",
            "  Args: {\"pattern\": \"search_term\", \"path\": \".\", \"file_pattern\": \"*.py\"}",
            "",
            "- directory_list: List directory contents",
            "  Args: {\"path\": \".\"}",
            "",
            "- system_info: Get system information",
            "  Args: {}",
            "",
            "- git_operations: Git commands",
            "  Args: {\"operation\": \"status|log|diff\"}",
            "",
            "- web_search: Search the web",
            "  Args: {\"query\": \"search term\"}",
            "",
            "- web_fetch: Fetch URL content",
            "  Args: {\"url\": \"https://example.com\"}",
            "",
            "AUTO-CHAIN BEHAVIOR:",
            "When you call file_search or directory_list, the system automatically reads the first result.",
            "You will receive BOTH the search results AND file contents in one response.",
            '"""',
            "",
            "# Training Examples",
            ""
        ]

        # Add training examples as MESSAGE blocks
        for idx, example in enumerate(self.training_data, 1):
            modelfile_content.append(f"# Example {idx}: {example.get('scenario', 'unknown')}")

            conversation = example.get("conversation", [])
            for turn in conversation:
                role = turn.get("role", "")
                content = turn.get("content", "")

                if role == "user":
                    modelfile_content.append(f'MESSAGE user """{content}"""')
                elif role == "assistant":
                    modelfile_content.append(f'MESSAGE assistant """{content}"""')
                # Skip system messages in Modelfile format

            modelfile_content.append("")

        # Write Modelfile
        with open(modelfile_path, 'w') as f:
            f.write('\n'.join(modelfile_content))

        return str(modelfile_path)

    def export_for_jsonl(self) -> str:
        """
        Export as JSONL format for generic fine-tuning tools
        Each line is a complete training example
        """
        jsonl_path = self.output_dir / "training_data.jsonl"

        with open(jsonl_path, 'w') as f:
            for example in self.training_data:
                # Convert conversation to messages format
                messages = []
                conversation = example.get("conversation", [])

                for turn in conversation:
                    role = turn.get("role", "")
                    content = turn.get("content", "")

                    if role in ["user", "assistant", "system"]:
                        messages.append({
                            "role": role,
                            "content": content
                        })

                # Write as single line JSON
                json_line = json.dumps({
                    "messages": messages,
                    "scenario": example.get("scenario", "unknown")
                })
                f.write(json_line + '\n')

        return str(jsonl_path)

    def export_for_huggingface(self) -> str:
        """
        Export in Hugging Face datasets format
        Compatible with transformers Trainer
        """
        hf_path = self.output_dir / "hf_training_data.json"

        hf_data = []
        for example in self.training_data:
            conversation = example.get("conversation", [])

            # Format for instruction fine-tuning
            user_messages = []
            assistant_messages = []

            for turn in conversation:
                role = turn.get("role", "")
                content = turn.get("content", "")

                if role == "user":
                    user_messages.append(content)
                elif role == "assistant":
                    assistant_messages.append(content)

            if user_messages and assistant_messages:
                hf_data.append({
                    "instruction": user_messages[0],
                    "input": "",
                    "output": assistant_messages[0],
                    "scenario": example.get("scenario", "unknown")
                })

        with open(hf_path, 'w') as f:
            json.dump(hf_data, f, indent=2)

        return str(hf_path)

    def create_training_script(self, model_name: str, base_model: str) -> str:
        """
        Create a shell script to run the fine-tuning
        """
        script_path = self.output_dir / "train_model.sh"

        modelfile_name = f"Modelfile_{model_name}"

        script_content = f"""#!/bin/bash
# OpenCode Tool Training - Fine-tuning Script
# Generated by OpenCode Tool Trainer

echo "=================================================="
echo "  OpenCode Tool Fine-Tuning"
echo "=================================================="
echo ""
echo "Model: {model_name}"
echo "Base Model: {base_model}"
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Error: Ollama is not installed"
    echo "Install from: https://ollama.ai"
    exit 1
fi

# Create the model with training data
echo "Creating fine-tuned model..."
ollama create {model_name} -f {modelfile_name}

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Model created successfully: {model_name}"
    echo ""
    echo "Test your model:"
    echo "  ollama run {model_name}"
    echo ""
    echo "Or use in OpenCode:"
    echo "  Edit config.yaml and set model.name: {model_name}"
else
    echo ""
    echo "✗ Model creation failed"
    exit 1
fi
"""

        with open(script_path, 'w') as f:
            f.write(script_content)

        # Make executable
        script_path.chmod(0o755)

        return str(script_path)

    def export_all(self, model_name: str, base_model: str) -> Dict[str, str]:
        """Export in all formats and create training script"""

        print(f"\n{'='*50}")
        print(f"  Exporting Training Data")
        print(f"{'='*50}\n")

        exports = {}

        # Ollama Modelfile
        print("📝 Creating Ollama Modelfile...")
        exports["modelfile"] = self.export_for_ollama(model_name, base_model)
        print(f"   ✓ {exports['modelfile']}")

        # JSONL format
        print("📝 Creating JSONL format...")
        exports["jsonl"] = self.export_for_jsonl()
        print(f"   ✓ {exports['jsonl']}")

        # Hugging Face format
        print("📝 Creating Hugging Face format...")
        exports["huggingface"] = self.export_for_huggingface()
        print(f"   ✓ {exports['huggingface']}")

        # Training script
        print("📝 Creating training script...")
        exports["script"] = self.create_training_script(model_name, base_model)
        print(f"   ✓ {exports['script']}")

        print(f"\n{'='*50}")
        print(f"  Export Complete!")
        print(f"{'='*50}\n")
        print(f"Output directory: {self.output_dir}")
        print(f"\nTo fine-tune with Ollama:")
        print(f"  cd {self.output_dir}")
        print(f"  ./train_model.sh")
        print(f"\nOr manually:")
        print(f"  ollama create {model_name} -f {self.output_dir}/Modelfile_{model_name}")

        return exports


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python export_for_finetuning.py <training_data.json>")
        sys.exit(1)

    # Load training data
    with open(sys.argv[1]) as f:
        data = json.load(f)

    # Export
    exporter = TrainingDataExporter(data, "./exports")
    exporter.export_all(
        model_name="opencode-tools-trained",
        base_model="qwen2.5-coder:1.5b"
    )
