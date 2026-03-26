# Proposal: Implementing Model Persistence and Profiling

## 1. Introduction and Rationale

This proposal outlines the implementation of robust model persistence (saving and loading trained model parameters) and comprehensive profiling (recording training metrics and hyperparameters) within the `Python-master` repository.

**Rationale:**
*   **Reproducibility:** Ensure that trained models can be recreated and reused consistently.
*   **Experiment Tracking:** Systematically record performance metrics and hyperparameters for comparing different model configurations and training runs.
*   **Deployment Readiness:** Facilitate saving trained models for later deployment or inference without retraining.
*   **Developer Workflow:** Streamline the process of developing and evaluating machine learning models.

## 2. Scope of Work

The scope of this proposal covers:
*   Standardizing the saving and loading of trained model weights and biases for selected key machine learning and neural network implementations.
*   Implementing mechanisms to capture and store profiling data (e.g., hyperparameters, final metrics, training loss/accuracy history) for these models.
*   Extending the `master.py` orchestrator script to manage these save, load, and profiling operations via command-line arguments.

## 3. Technical Approach

### 3.1. Serialization Formats

*   **Model Weights/Parameters:**
    *   **`joblib`**: Preferred for `numpy` arrays and `scikit-learn` objects due to efficiency.
    *   **`pickle`**: Suitable for custom Python classes where the entire object state needs to be preserved (e.g., custom neural network layers).

*   **Profiling Data (Metrics & History):**
    *   **`JSON` (.json):** For structured, human-readable summaries of a training run (e.g., hyperparameters, final accuracy, execution time).
    *   **`CSV` (.csv):** For tabular training history (e.g., epoch-by-epoch loss, error, or other metrics).

### 3.2. Modifications to Submodules

For each relevant ML/NN class/script, the following will be implemented or adapted:

*   **`save_model(self, file_path: str)` method (or function):** Serializes the model's learned parameters (weights, biases, etc.) to `file_path`.
*   **`load_model(cls, file_path: str)` class method (or function):** Deserializes the model's parameters from `file_path` and reconstructs/returns a model instance.
*   **Exposing Training History:** Ensure that training functions return or provide access to metrics collected during training (e.g., a list of loss values per epoch).

**Example Submodules for Initial Implementation/Adaptation:**

*   **`neural_network/convolution_neural_network.py`**: Adapt existing `save_model` and `read_model` methods to align with the proposed `joblib` standard for weights (if applicable, otherwise keep `pickle`).
*   **`machine_learning/linear_regression.py`**: Refactor into a class-based model if not already, and add `save_model`/`load_model` for its `theta` (weights) using `joblib` or `numpy.save`. If keeping as a procedural script, the `theta` could be saved/loaded directly.
*   **`neural_network/back_propagation_neural_network.py`**: Add `save_model`/`load_model` for `DenseLayer` weights/biases. Ensure `BPNN.train` explicitly returns or stores `self.train_mse` for external saving.
*   **`machine_learning/k_means_clust.py`**: Add `save_model`/`load_model` for `centroids` using `joblib`. Ensure `kmeans` function returns `heterogeneity` list for external saving.

### 3.3. Modifications to `master.py` (Orchestrator)

The `master.py` script will be enhanced to provide a unified interface for these operations:

*   **New Command-Line Arguments for each relevant subcommand:**
    *   `--save-model <path>`: Specify a path to save the trained model.
    *   `--load-model <path>`: Specify a path to load a pre-trained model.
    *   `--save-metrics <path>`: Specify a `.json` path to save a summary of hyperparameters and final performance metrics.
    *   `--save-history <path>`: Specify a `.csv` path to save detailed epoch-by-epoch training history.

*   **Orchestration Logic in Wrapper Functions:**
    *   **Conditional Model Loading:** If `--load-model` is provided, the wrapper will call the submodule's `load_model` method. Otherwise, a new model instance is created.
    *   **Conditional Model Saving:** If `--save-model` is provided after training, the wrapper will call the submodule's `save_model` method.
    *   **Profiling Data Collection and Saving:** After a run (training or evaluation), the wrapper will collect relevant metrics and history (e.g., `model.train_mse`, `kmeans_heterogeneity`). It will then write this data to the specified `--save-metrics` (JSON) and `--save-history` (CSV) paths.

## 4. Example Usage

Here’s how a user would interact with the extended `master.py`:

```bash
# Train a Linear Regression model and save it, along with metrics
python master.py linear_regression 
    --save-model "models/linear_regression_v1.joblib" 
    --save-metrics "metrics/linear_regression_v1_summary.json"

# Load the trained Linear Regression model to make predictions (assuming linear_regression.py is refactored for prediction with a loaded model)
python master.py linear_regression 
    --load-model "models/linear_regression_v1.joblib" 
    --predict-data "path/to/new_data.csv" # (Hypothetical new argument for prediction)

# Train a K-Means model, saving the centroids and clustering history
python master.py kmeans --k-clusters 5 --max-iterations 200 --plot 
    --save-model "models/kmeans_k5_v1.joblib" 
    --save-history "history/kmeans_k5_v1_heterogeneity.csv" 
    --save-metrics "metrics/kmeans_k5_v1_summary.json"

# Train a BPNN model, saving weights and detailed MSE history
python master.py train_bpnn --epochs 50 --accuracy 0.005 
    --save-model "models/bpnn_model_v2.pkl" 
    --save-history "history/bpnn_training_mse_v2.csv" 
    --save-metrics "metrics/bpnn_training_v2_summary.json"
```

## 5. Benefits

*   **Enhanced Reproducibility:** Easily reload specific model versions.
*   **Systematic Experimentation:** Compare model performance across different runs and hyperparameter choices with structured metrics.
*   **Streamlined Deployment:** Prepare models for production by saving their final state.
*   **Improved Code Reusability:** Encourage a modular design where models can be trained, saved, and loaded independently of the training script.
