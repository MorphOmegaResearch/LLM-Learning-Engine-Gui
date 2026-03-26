# Clipboard Assistant

A simple desktop tool to process clipboard content with local LLMs via the Ollama API.

## Features

- **Clipboard Integration**: Read content directly from your system's clipboard with an auto-refresh option.
- **AI Processing**: Send clipboard text along with custom instructions to a local language model running via Ollama.
- **Real-time Interaction**: AI responses are streamed in real-time, and you can stop the generation at any point.
- **File Operations**: Load text from files into the input area and save AI-generated output to files using your system's native file browser.
- **Quick Actions**: Use pre-defined prompts for common tasks like summarizing, improving grammar, or explaining text.
- **Configuration**: Easily configure Ollama settings like the target model, server URL, and the number of GPU layers to use.
- **GPU Monitoring**: A basic monitor in the settings tab to show GPU usage (currently supports AMD GPUs via `radeontop`).

## How to Use

### 1. Prerequisites

- Python 3
- Ollama installed and running. You can download it from [ollama.ai](https://ollama.ai/).
- At least one model pulled (e.g., `ollama run llama2`).

### 2. Installation

The application requires a couple of Python packages. You can install them using pip:

```bash
pip install pyperclip requests
```

### 3. Running the Application

Navigate to the application directory and run the `clip.py` script:

```bash
python /path/to/quick_clip/clip.py
```

### 4. Using the Tabs

- **📋 Read Tab**: Shows the current content of your clipboard. You can manually refresh or enable auto-refresh. From here, you can quickly send the content to the 'Edit & Process' tab.
- **✏️ Edit & Process Tab**: This is where you interact with the AI.
    - The top "Input" section is for the text you want to process. You can load it from the clipboard, type it in, or load it from a file.
    - The "Instructions/Prompt" box is where you tell the AI what to do.
    - Click "🚀 Send" to start the AI processing. Click "⏹️ Stop" to interrupt it.
    - The "AI Output" section will show the result in real-time. You can copy the output or save it to a file.
- **⚙️ Settings Tab**:
    - **Ollama Settings**: Change the model, server URL, and clipboard refresh interval. You can test the connection and fetch a list of all available models from your Ollama server.
    - **GPU Settings**: Specify how many GPU layers the model should use. Leave blank for Ollama to decide.
    - **GPU Monitoring**: See basic usage stats for your GPU.

### 5. Creating a Desktop Launcher (Example for XFCE)

For quick access, you can add a launcher to your desktop or panel.

1.  Right-click your desktop or panel and look for an option like "Add New Items" or "Create Launcher".
2.  When prompted for the command, enter the full path to run the script:
    ```
    python /home/commander/Desktop/quick_clip/clip.py
    ```
3.  Give it a name (e.g., "Clip Assistant") and save it. You can also assign an icon if you wish.
