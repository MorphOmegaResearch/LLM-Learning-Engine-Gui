# Python-master

This directory contains various Python implementations of algorithms and data structures across different domains.

## Machine Learning

The `machine_learning` directory provides implementations of a wide array of machine learning algorithms, covering both supervised and unsupervised learning paradigms, as well as various utility functions and advanced concepts.

*   **Supervised Learning:**
    *   `decision_tree.py`: Implements a basic regression decision tree, mapping real number inputs to real number outputs, useful for understanding tree-based learning.
    *   `gaussian_naive_bayes.py.broken.txt`: Demonstrates Gaussian Naive Bayes classification using the Iris dataset with scikit-learn, useful for probabilistic classification.
    *   `gradient_boosting_classifier.py`: Implements a Gradient Boosting Classifier, building an ensemble of weak learners (decision trees) to improve predictive accuracy for classification tasks.
    *   `linear_regression.py`: Provides an implementation of linear regression, including dataset collection (CSGO data), gradient descent for optimization, and sum of square error calculation.
    *   `logistic_regression.py`: Implements logistic regression from scratch for binary classification, featuring sigmoid function and cost function definitions, and a training loop using gradient descent.
    *   `multilayer_perceptron_classifier.py`: Uses `sklearn.neural_network.MLPClassifier` to demonstrate a Multilayer Perceptron for classification, showcasing library usage for basic neural networks.
    *   `random_forest_classifier.py`: Utilizes `sklearn.ensemble.RandomForestClassifier` for classification on the Iris dataset, illustrating ensemble learning.
    *   `support_vector_machines.py`: Implements a Support Vector Classifier (SVC) from scratch, including linear and RBF kernels, and uses Wolfe's Dual to calculate optimal parameters.
    *   `xgboost_classifier.py`: Demonstrates the usage of `xgboost.XGBClassifier` for classification on the Iris dataset, highlighting a popular gradient boosting framework.

*   **Unsupervised Learning:**
    *   `k_means_clust.py`: Implements the K-Means clustering algorithm, including functions for initializing centroids, assigning clusters, revising centroids, and computing heterogeneity.
    *   `principle_component_analysis.py`: Implements Principal Component Analysis (PCA) for dimensionality reduction, including data standardization and computation of principal components using SVD.
    *   `apriori_algorithm.py`: Implements the Apriori algorithm for association rule mining (market basket analysis), used to find frequent itemsets in transactional databases.

*   **Other ML Concepts & Utilities:**
    *   `forecasting/run.py`: (Needs further inspection within the `forecasting` directory to determine exact role, but likely contains time series forecasting logic).
    *   `gradient_descent.py`: A generic implementation of the gradient descent algorithm for minimizing the cost of a linear hypothesis function.
    *   `loss_functions.py`: Defines various loss functions crucial for training machine learning models, including binary cross-entropy, categorical cross-entropy, hinge loss, Huber loss, MSE, MAE, MSLE, MAPE, perplexity, and smooth L1 loss.
    *   `scoring_functions.py`: Provides implementations of common scoring metrics such as Mean Absolute Error (MAE), Mean Squared Error (MSE), Root Mean Squared Error (RMSE), Root Mean Square Logarithmic Error (RMSLE), and Mean Bias Deviation (MBD).

## Neural Networks

The `neural_network` directory focuses on the implementation of various artificial neural network architectures and their foundational components.

*   **Neural Network Models:**
    *   `simple_neural_network.py`: Implements a very basic neural network with a single neuron and forward propagation using a sigmoid activation function, primarily for conceptual understanding and demonstrating weight updates.
    *   `perceptron.py.DISABLED`: Implements a Perceptron for binary classification, showcasing its training and sorting capabilities using a sign activation function.
    *   `two_hidden_layers_neural_network.py`: Implements a feedforward neural network with two hidden layers, including feedforward and backpropagation mechanisms using NumPy for weight updates and sigmoid activation.
    *   `back_propagation_neural_network.py`: Provides a framework for a Back Propagation Neural Network (BPNN) with `DenseLayer` objects, supporting multiple layers and customizable activation functions and learning rates, for advanced network construction.
    *   `convolution_neural_network.py`: Implements a Convolutional Neural Network (CNN) with convolution and pooling layers, designed for image recognition tasks like handwriting word recognition.
    *   `gan.py_tf`: Implements a Generative Adversarial Network (GAN) using NumPy (despite the `_tf` suffix, the code provided is NumPy-based), including discriminator and generator networks with various activation functions, and an Adam optimizer.

*   **Components:**
    *   `activation_functions/`: This subdirectory contains various activation functions essential for neural networks:
        *   `binary_step.py`: Binary step activation function.
        *   `exponential_linear_unit.py`: Exponential Linear Unit (ELU).
        *   `gaussian_error_linear_unit.py`: Gaussian Error Linear Unit (GELU).
        *   `leaky_rectified_linear_unit.py`: Leaky Rectified Linear Unit (Leaky ReLU).
        *   `mish.py`: Mish activation function.
        *   `rectified_linear_unit.py`: Rectified Linear Unit (ReLU).
        *   `scaled_exponential_linear_unit.py`: Scaled Exponential Linear Unit (SELU).
        *   `soboleva_modified_hyperbolic_tangent.py`: Soboleva Modified Hyperbolic Tangent (SMHT).
        *   `softplus.py`: Softplus activation function.
        *   `squareplus.py`: Squareplus activation function.
        *   `swish.py`: Swish activation function.

These modules serve as practical examples and building blocks for understanding and applying advanced computational intelligence techniques.

## General Assistant Capabilities

This section outlines various modules that could contribute to building a versatile general-purpose assistant, covering areas from natural language processing and data handling to computational logic and web interaction.

*   **Audio Processing (`audio_filters/`)**:
    *   `butterworth_filter.py`, `iir_filter.py`: Essential for processing audio input (e.g., for voice commands, sound analysis) by applying various signal filters.
    *   `equal_loudness_filter.py.broken.txt`: Potentially useful for normalizing audio levels.

*   **Problem Solving & Logic (`backtracking/`)**:
    *   `sudoku.py`, `n_queens.py`, `crossword_puzzle_solver.py`: Provides algorithms for solving logic puzzles and constraint satisfaction problems, applicable to various planning or deduction tasks.
    *   `all_combinations.py`, `all_permutations.py`: Useful for generating sets of possibilities, crucial for decision-making processes.
    *   `word_break.py`, `word_ladder.py`, `word_search.py`: Algorithms for linguistic problem-solving and text manipulation.

*   **Low-Level Data Handling (`bit_manipulation/`)**:
    *   `is_even.py`, `count_setbits.py`: Basic data checks and efficient low-level computations.
    *   `binary_to_decimal.py`, `gray_code_sequence.py`: Utilities for converting and encoding/decoding data.

*   **Logical Reasoning (`boolean_algebra/`)**:
    *   `and_gate.py`, `or_gate.py`, `not_gate.py`, `xor_gate.py`: Fundamental logic operations necessary for decision-making and rule-based systems.
    *   `karnaugh_map_simplification.py`, `quine_mc_cluskey.py`: Algorithms for simplifying complex logical expressions, useful for optimizing internal decision flows.

*   **Security & Encoding (`ciphers/`)**:
    *   `caesar_cipher.py`, `vigenere_cipher.py`, `rsa_cipher.py`: Implementations of various ciphers for data encryption, decryption, and secure communication.
    *   `base64_cipher.py`, `morse_code.py`: Utilities for encoding and decoding data formats.

*   **Visual Processing (`computer_vision/`, `digital_image_processing/`)**:
    *   `cnn_classification.py` (in `computer_vision`): For image classification tasks, enabling the assistant to "see" and interpret visual input.
    *   `harris_corner.py`, `intensity_based_segmentation.py` (in `computer_vision`): For feature detection and analysis within images.
    *   `change_brightness.py`, `change_contrast.py`, `sepia.py` (in `digital_image_processing`): For manipulating and enhancing images.
    *   `edge_detection`, `filters` (subdirectories in `digital_image_processing`): For advanced image analysis and feature extraction.

*   **Data Conversion (`conversions/`)**:
    *   `binary_to_decimal.py`, `decimal_to_any.py`, `hexadecimal_to_decimal.py`, `octal_to_binary.py`: Extensive number system conversions.
    *   `temperature_conversions.py`, `length_conversion.py`, `weight_conversion.py`, `speed_conversions.py`, `volume_conversions.py`, `energy_conversions.py`, `pressure_conversions.py`, `time_conversions.py`, `astronomical_length_scale_conversion.py`: Comprehensive unit conversion capabilities for practical queries.
    *   `roman_numerals.py`, `convert_number_to_words.py`: For converting numbers to and from various textual representations.
    *   `rgb_cmyk_conversion.py`, `rgb_hsv_conversion.py`: Color model conversions.

*   **Data Compression (`data_compression/`)**:
    *   `huffman.py`, `lempel_ziv.py`, `lz77.py`, `run_length_encoding.py`, `burrows_wheeler.py`: Algorithms for efficient storage and transfer of information, useful for handling large datasets or optimizing communication.

*   **Data Structures (`data_structures/`)**:
    *   `arrays`, `binary_tree`, `disjoint_set`, `hashing`, `heap`, `kd_tree`, `linked_list`, `queues`, `stacks`, `suffix_tree`, `trie`: Fundamental building blocks for efficient data management, storage, and retrieval, crucial for any complex system. `trie` is particularly useful for autocomplete and dictionary functions.

*   **Algorithmic Efficiency (`divide_and_conquer/`, `dynamic_programming/`, `greedy_methods/`)**:
    *   `mergesort.py`, `max_subarray.py` (in `divide_and_conquer`): Efficient data processing and problem-solving strategies.
    *   `(dynamic_programming/)`: Contains solutions to optimization problems by breaking them into simpler subproblems, useful for complex planning and decision-making where optimal solutions are required.
    *   `minimum_coin_change.py`, `fractional_knapsack.py` (in `greedy_methods`): Algorithms for resource allocation and making locally optimal choices.

*   **File System Interaction (`file_transfer/`)**:
    *   `send_file.py`, `receive_file.py`: Basic functionalities for interacting with the local file system, allowing the assistant to handle files.

*   **Financial Calculations (`financial/`)**:
    *   `interest.py`, `equated_monthly_installments.py`, `simple_moving_average.py`: Provides tools for basic financial calculations, enabling the assistant to answer financial queries or perform simple analyses.

*   **Geometric Calculations (`geometry/`)**:
    *   `geometry.py`: Provides basic geometric calculation capabilities for spatial reasoning or answering related questions.

*   **Graph & Network Analysis (`graphs/`, `networking_flow/`)**:
    *   `a_star.py`, `dijkstra_algorithm.py`, `breadth_first_search.py`, `depth_first_search.py`: Comprehensive set of algorithms for pathfinding, navigation, and searching through connected data, vital for routing, recommendation systems, or understanding relationships.
    *   `page_rank.py`: Algorithm for ranking the importance of nodes in a network.
    *   `minimum_spanning_tree_kruskal.py`: For network optimization and connectivity problems.
    *   `ford_fulkerson.py`, `minimum_cut.py` (in `networking_flow`): Algorithms for analyzing network capacity and resource flow.

*   **Hashing & Data Integrity (`hashes/`)**:
    *   `md5.py`, `sha1.py`, `sha256.py`: Implementations of hashing algorithms for ensuring data integrity, unique identification, and secure storage (e.g., passwords).
    *   `luhn.py`: Algorithm for validating identification numbers like credit card numbers.

*   **Linear Algebra (`linear_algebra/`)**:
    *   `gaussian_elimination.py`, `matrix_inversion.py`: Essential mathematical tools for solving systems of linear equations and performing transformations, foundational for many data analysis and machine learning tasks.

*   **General Mathematics (`maths/`)**:
    *   `basic_maths.py`, `factorial.py`, `prime_check.py`, `gcd_of_n_numbers.py`, `combinations.py`: A wide array of fundamental arithmetic, number theory, and combinatorial calculation functions.
    *   `euclidean_distance.py`, `manhattan_distance.py`: Distance calculation methods applicable in various scenarios (e.g., similarity measures).

*   **Matrix Operations (`matrix/`)**:
    *   `matrix_operation.py`, `matrix_class.py`: Core utilities for manipulating and performing operations on matrices, useful for data transformations and computational tasks.
    *   `rotate_matrix.py`, `searching_in_sorted_matrix.py`: Algorithms for organizing and searching within matrix-structured data.

*   **Miscellaneous Utilities (`other/`)**:
    *   `activity_selection.py`: For scheduling tasks efficiently.
    *   `lru_cache.py`, `lfu_cache.py`: Implementations of caching mechanisms to improve performance and efficiency of frequently accessed data.
    *   `password.py`: Utilities for password generation or validation.
    *   `tower_of_hanoi.py`: A classic problem-solving example.

*   **Searching Algorithms (`searches/`)**:
    *   `binary_search.py`, `linear_search.py`, `exponential_search.py`, `jump_search.py`, `interpolation_search.py`, `ternary_search.py`: A diverse set of algorithms for efficiently retrieving specific information from structured or unstructured data.

*   **Sorting Algorithms (`sorts/`)**:
    *   `bubble_sort.py`, `quick_sort.py`, `merge_sort.py`, `heap_sort.py`, `radix_sort.py`, and many others: A comprehensive collection of algorithms for organizing and ordering data, essential for presentation, analysis, and efficient processing.

*   **String Processing & NLP Fundamentals (`strings/`)**:
    *   `palindrome.py`, `anagrams.py`, `count_vowels.py`, `reverse_words.py`: Basic text manipulation and analysis functions.
    *   `levenshtein_distance.py`, `jaro_winkler.py`: Algorithms for calculating string similarity, crucial for fuzzy matching, spell checking, and query correction.
    *   `aho_corasick.py`, `knuth_morris_pratt.py`, `rabin_karp.py`: Efficient algorithms for searching for patterns within text, foundational for text parsing and command recognition.
    *   `is_valid_email_address.py`, `credit_card_validator.py`: Utilities for validating various input formats.
    *   `autocomplete_using_trie.py`: Leveraging the Trie data structure for predictive text and search suggestions.

*   **Web Interaction & Data Fetching (`web_programming/`)**:
    *   `currency_converter.py`, `current_weather.py`, `fetch_bbc_news.py`, `get_imdb_top_250_movies_csv.py`, `nasa_data.py`, `reddit.py`, `search_books_by_isbn.py`, `world_covid19_stats.py`: A wide range of scripts for fetching real-world data and information from various online sources.
    *   `crawl_google_results.py`, `emails_from_url.py`: Web scraping capabilities for extracting specific information from web pages.

This comprehensive overview outlines how various modules within this repository can be leveraged to build a robust and versatile general-purpose assistant.

## LLM Fine-Tuning and Evaluation Pipeline (`train/`)

This directory contains a complete pipeline for fine-tuning Large Language Models (LLMs) for tool usage, evaluating their performance, and preparing them for deployment. This suite leverages frameworks like Unsloth, Hugging Face Transformers, and PEFT.

*   **`training_data_generator.py`**: **(Data Alpha)** This script is responsible for generating synthetic training data for various tool-use scenarios. It defines conversation flows, tool schemas, and creates multi-turn examples involving tool calls and system responses, crucial for fine-tuning LLMs to interact with external tools. It also generates baseline skill tests and error recovery examples.

*   **`split_training_data.py`**: A utility script for organizing generated (or collected) training data. It takes a monolithic JSONL file and splits it into categorized JSONL files based on scenario mappings, allowing for more targeted training and evaluation of specific skill sets.

*   **`training_engine.py`**: **(Training Orchestrator)** This is the core fine-tuning orchestrator. It handles the end-to-end training process:
    *   Loads a base language model (optimized with Unsloth or standard Hugging Face Transformers).
    *   Applies Parameter-Efficient Fine-Tuning (PEFT) using LoRA adapters.
    *   Loads and preprocesses training data from JSONL files, converting conversations into chat templates.
    *   Configures and executes the `SFTTrainer` (from TRL library).
    *   Saves the trained LoRA adapter.
    *   Records comprehensive training statistics.
    *   Integrates directly with the `evaluation_engine.py` for post-training performance assessment.
    *   Includes features like time limits, early stopping, and mixed precision training.

*   **`train_with_unsloth.py`**: This script provides a more direct, possibly legacy, entry point for Unsloth-based training. While `training_engine.py` is the primary orchestrator, this script demonstrates the foundational steps of Unsloth model loading, LoRA application, data loading, and trainer setup for a specific training run.

*   **`evaluation_engine.py`**: **(Evaluation Omega)** This robust component is dedicated to evaluating trained models. It:
    *   Loads various test suites (collections of JSONL-formatted test cases).
    *   Executes test cases by making inference calls to the target model (e.g., via Ollama API).
    *   Scores the model's responses against expected tool calls and arguments using various policies (e.g., `exact_match`, `args_subset`).
    *   Generates detailed reports, including pass rates, per-skill/category metrics, confusion matrices, and behavior scores.
    *   Provides functionalities for comparing model performance against baselines, detecting regressions, and suggesting corrective training data.

*   **`merge_and_export.py`**: **(Deployment Omega - Merge)** This script facilitates deployment by merging a fine-tuned LoRA adapter back into its original base model. It then exports the consolidated model into the GGUF format, which is highly efficient for local inference with tools like `llama.cpp` and Ollama. It supports both Unsloth (GPU) and a CPU-only fallback for the merging and conversion process.

*   **`export_base_to_gguf.py`**: **(Deployment Omega - Base Export)** A utility focused on the direct conversion of a base (non-LoRA) PyTorch model to the GGUF format. This is useful for making foundational models available for local inference without any prior fine-tuning or adapter merging.

This comprehensive pipeline enables the end-to-end development, evaluation, and deployment of LLM-based tool-use agents within this repository.
