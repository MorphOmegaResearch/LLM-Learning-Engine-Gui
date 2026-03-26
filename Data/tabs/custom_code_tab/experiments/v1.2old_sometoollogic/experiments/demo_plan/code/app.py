from argparse import ArgumentParser
import os
import json
import re
from pathlib import Path
from typing import List, Dict

def parse_heading(text: str) -> str:
    """Parses the first H1 heading for a note and returns it as a slug."""
    match = re.search(r'## (.*)', text)
    if match:
        return match.group(1).strip()
    else:
        return os.path.basename(text)  # Fallback to filename

def generate_slug(title: str) -> str:
    """Generates a slug from the note title."""
    return re.sub(r'[^a-zA-Z0-9\s]', '', title).replace(' ', '-').lower()


def convert_markdown(filepath: Path) -> str:
    """Converts markdown content to HTML, keeping headings and code blocks."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        # Basic HTML conversion (no external dependencies)
        html_content = ""
        for heading in re.findall(r'##\s*(.*)', content):
            html_content += f"<h1 class='heading'>{heading}</h1>"
        for code_block in re.findall(r'