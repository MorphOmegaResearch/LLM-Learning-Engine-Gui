# OpenCode Trainer System - Help Guide

## 1. Introduction

This guide provides a comprehensive overview of the OpenCode Trainer System, a modular application designed to fine-tune small language models (1.5B-4B parameters) with LoRA adapters for using OpenCode tools. It details the system's architecture, key components, and step-by-step instructions for initiating and managing training sessions.

## 2. Overall Training Workflow

The typical workflow for training a model involves the following steps within the GUI:

1.  **Launch the Application**: Start the `interactive_trainer_gui_NEW.py` application.
2.  **Navigate to the Training Tab**: Select the "Training" tab.
3.  **Select a Category and Script**: In the "Categories" sub-tab, choose a training category and the specific `train.py` script you wish to run.
4.  **Configure Training Parameters**: In the "Configuration" sub-tab, set parameters such as training runs (epochs), batch size, learning strength, and the base model.
5.  **Select Datasets**: In the "Dataset" sub-tab, select the `.jsonl` files that will be used for training.
6.  **Review Summary**: In the "Summary" sub-tab, review your selections and estimated training details.
7.  **Start Training**: In the "Runner" sub-tab, click the "Start Training" button.
8.  **Monitor Output**: Observe the live output of the training process in the "Runner" sub-tab.
9.  **Post-Training Actions**: Once training is complete, check the "Models" tab for the newly trained model and statistics.

## 3. Core Components and Their Functions

This section details the main Python files and their critical functions, focusing on their role in the training process.

### 3.1. `Data/interactive_trainer_gui_NEW.py` (Main Coordinator)

*   **Role**: This is the main entry point for the GUI application. It initializes the Tkinter root window, sets up the overall theme, and orchestrates the loading and display of all modular tabs (Training, Models, Settings).

### 3.2. `Data/tabs/training_tab/training_tab.py` (Training Tab Coordinator)

*   **Role**: Manages all sub-panels related to the training process. It acts as a central hub for the "Training" tab, instantiating `RunnerPanel`, `CategoryManagerPanel`, `DatasetPanel`, `ConfigPanel`, `ProfilesPanel`, and `SummaryPanel`.
*   **`create_ui()`**: Initializes and lays out the user interface for the entire Training tab, including its sub-tabs.
*   **`post_training_actions()`**: (Newly added) This method is called after a training session completes. It's designed to handle follow-up tasks such as refreshing the Models tab or displaying a completion message.

### 3.3. `Data/tabs/training_tab/runner_panel.py` (Training Runner Panel)

*   **Role**: Responsible for initiating, monitoring, and stopping the training process. It gathers all necessary configurations from other panels and executes the selected training script.
*   **`create_ui()`**: Sets up the UI for the Runner panel, including the "Start Training" and "Stop Training" buttons, and the live output display.
*   **`start_training()`**: This is the core function that orchestrates the launch of a training session.
    *   It retrieves the selected category and script from `CategoryManagerPanel`.
    *   It fetches training parameters from `ConfigPanel`.
    *   It gets selected datasets from `DatasetPanel`.
    *   It prepares environment variables based on these settings.
    *   It executes the chosen `train.py` script in a separate thread using `subprocess.Popen`.
    *   It logs the output to the UI and calls `post_training_actions()` upon completion.
*   **`stop_training()`**: Terminates the currently running training process.
*   **`_run_training_process(command, env_vars)`**: An internal method that executes the training script as a subprocess and streams its output to the UI.

### 3.4. `Data/tabs/training_tab/category_manager_panel.py` (Category Manager Panel)

*   **Role**: Allows users to view, select, and manage training categories and their associated scripts and JSONL files. It also provides an editor for scripts and JSONL files.
*   **`create_ui()`**: Builds the UI for category selection, script/JSONL file listing, and the integrated code editor.
*   **`populate_category_dropdown()`**: Fills the category selection dropdown with available training categories.
*   **`on_category_selected()`**: Updates the panel when a new category is selected, populating the JSONL file list.
*   **`get_selected_category()`**: (Newly added) Returns the name of the currently selected training category.
*   **`get_selected_script()`**: (Newly added) Returns the filename of the currently selected training script (`train.py`) in the editor.

### 3.5. `Data/tabs/training_tab/dataset_panel.py` (Dataset Panel)

*   **Role**: Enables users to select specific categories and subcategories of training data (`.jsonl` files).
*   **`create_ui()`**: Constructs the UI with checkboxes for categories and subcategories.
*   **`create_category_section(parent, category)`**: Dynamically creates UI elements for a given training category, including checkboxes for its subcategories.
*   **`get_selected_datasets()`**: (Newly added) Returns a list of absolute file paths to the `.jsonl` files selected by the user. If a category is selected but no specific subcategories are chosen, it includes all `.jsonl` files within that category.

### 3.6. `Data/tabs/training_tab/config_panel.py` (Configuration Panel)

*   **Role**: Provides controls for setting various training parameters such as epochs, batch size, learning rate, and the base model.
*   **`create_ui()`**: Lays out the UI elements (spinboxes, entry fields, comboboxes) for configuring training parameters.
*   **`get_config_params()`**: (Newly added) Returns a dictionary containing the current values of all configured training parameters.

### 3.7. `Data/config.py` (Central Configuration & Utilities)

*   **Role**: A utility module providing functions for path management, discovering categories, listing Ollama models, and managing training profiles and statistics.
*   **`get_category_info()`**: Retrieves information about available training categories and their associated data.
*   **`get_ollama_models()`**: Fetches a list of available Ollama models from the system.
*   **`save_training_stats()`**: Saves statistics after a training run.
*   **`create_category_folder(category_name)`**: Creates a new folder for a training category.
*   **`create_subcategory_file(parent_category, subcategory_name)`**: Creates a new `.jsonl` file for a subcategory.

### 3.8. `Data/training_engine.py` (Core Training Engine)

*   **Role**: This is the reusable Python library that encapsulates the core logic for fine-tuning models using Unsloth. Category-specific `train.py` scripts import and utilize the `TrainingEngine` class.
*   **`TrainingEngine` class**:
    *   **`__init__(config)`**: Initializes the engine with a configuration dictionary.
    *   **`load_model()`**: Loads the base model and prepares LoRA adapters.
    *   **`load_training_data()`**: Processes the input `.jsonl` files into a format suitable for training.
    *   **`setup_trainer()`**: Configures the `SFTTrainer` from Unsloth.
    *   **`train()`**: Executes the actual fine-tuning process.
    *   **`save_model()`**: Saves the trained model.
    *   **`export_gguf()`**: Exports the model to the GGUF format for Ollama.
    *   **`run_full_training()`**: Orchestrates the entire training pipeline from data loading to model export.

### 3.9. `Training_Data-Sets/*/train.py` (Category-Specific Training Scripts)

*   **Role**: These are small Python scripts located within each category folder (e.g., `Training_Data-Sets/Tools/train.py`). They act as wrappers that:
    1.  Discover `.jsonl` files in their respective category.
    2.  Combine them into a temporary file.
    3.  Create a configuration dictionary, often leveraging environment variables set by the GUI.
    4.  Instantiate and call `TrainingEngine.run_full_training()` to start the training.

## 4. How to Use the Trainer

### 4.1. Launching the GUI

To start the application, run the main GUI script:

```bash
python3 Data/interactive_trainer_gui_NEW.py
```

### 4.2. Configuring a Training Session

1.  **Training Tab**: Once the GUI is open, navigate to the "Training" tab.
2.  **Categories Sub-tab**:
    *   Use the dropdown to select the category you want to train (e.g., "Tools", "Coding").
    *   Ensure the `train.py` script for that category is selected in the editor if you wish to view/edit it.
3.  **Configuration Sub-tab**:
    *   **Training Runs**: Set the number of epochs (how many times the model will see the entire dataset).
    *   **Batch Size**: Define the number of examples processed per training step.
    *   **Learning Strength**: Adjust the learning rate for the model.
    *   **Base Model**: Select the base Ollama model you wish to fine-tune from the dropdown.
4.  **Dataset Sub-tab**:
    *   Check the boxes next to the categories and subcategories whose `.jsonl` files you want to include in the training data.
    *   If a category is checked but no specific subcategories are, all `.jsonl` files within that category will be used.
5.  **Summary Sub-tab**: Review the selected categories, total examples, and configuration parameters to ensure everything is as expected.

### 4.3. Starting and Monitoring Training

1.  **Runner Sub-tab**: Navigate to the "Runner" sub-tab.
2.  **Start Training**: Click the "Start Training" button.
3.  **Live Output**: The terminal-style display in the Runner panel will show the live output from the training script. Monitor this for progress and any errors.
4.  **Completion**: A message box will appear when training is complete.

### 4.4. Post-Training

After training, the newly fine-tuned model will be saved in the `Models/` directory. You can then navigate to the "Models" tab to view details, notes, and statistics about your trained models.

## 5. Troubleshooting

For common issues and their solutions, please refer to the `BluePrint.txt` file in the root directory, specifically Section 9: "Troubleshooting". It covers GUI issues, training issues, and module import issues.
