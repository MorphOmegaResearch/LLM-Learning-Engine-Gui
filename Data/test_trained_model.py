#!/usr/bin/env python3
"""
Test the trained model
"""

import torch
from unsloth import FastLanguageModel

MODEL_PATH = "./trained_model"
MAX_SEQ_LENGTH = 2048

print("=" * 60)
print("  Testing Trained Model")
print("=" * 60)
print()

print(f"📦 Loading model from: {MODEL_PATH}")

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_PATH,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=True,
)

# Enable fast inference
FastLanguageModel.for_inference(model)

print("✓ Model loaded")
print()

# Test prompts
test_prompts = [
    "Create a file called test.txt with hello world",
    "Find all Python files",
    "Show system info",
    "Change version 1.0 to 2.0 in config.yaml",
    "Read the README file",
]

print("🧪 Running tests...")
print("=" * 60)
print()

for i, prompt in enumerate(test_prompts, 1):
    print(f"Test {i}/{len(test_prompts)}")
    print(f"User: {prompt}")

    # Format as chat
    messages = [{"role": "user", "content": prompt}]

    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to("cuda" if torch.cuda.is_available() else "cpu")

    # Generate
    outputs = model.generate(
        input_ids=inputs,
        max_new_tokens=256,
        temperature=0.3,
        do_sample=True,
        pad_token_id=tokenizer.eos_token_id
    )

    response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)

    print(f"Assistant: {response}")

    # Check if response contains tool call
    if '{"type":"tool_call"' in response:
        print("✓ Valid tool call detected")
    else:
        print("⚠️  No tool call found")

    print()

print("=" * 60)
print("  Testing Complete!")
print("=" * 60)
