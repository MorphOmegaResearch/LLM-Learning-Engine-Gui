import json
import os
import random
import re
from datetime import datetime

class ConversationalTrainer:
    """
    Integrates benchmark training data into the Linguistic Hierarchy.
    Focuses on response sequence validation and property-based scoring.
    """
    def __init__(self, training_dir, orchestrator=None):
        self.training_dir = training_dir
        self.orchestrator = orchestrator
        self.benchmarks = self._load_benchmarks()

    def _load_benchmarks(self):
        benchmarks = []
        for root, _, files in os.walk(self.training_dir):
            for file in files:
                if file.endswith(".json"):
                    with open(os.path.join(root, file), 'r') as f:
                        data = json.load(f)
                        if "benchmark_conversations" in data:
                            benchmarks.extend(data["benchmark_conversations"])
                        elif "quick_benchmarks" in data:
                            benchmarks.extend(data["quick_benchmarks"])
        return benchmarks

    def evaluate_response(self, input_text, response_text, domain="general"):
        """
        Scores a response against the most relevant benchmark.
        """
        # 1. Find best benchmark match
        best_match = None
        max_overlap = 0
        input_words = set(input_text.lower().split())
        
        for b in self.benchmarks:
            # Check the first learner turn in the benchmark
            benchmark_utterance = ""
            if "conversation" in b:
                benchmark_utterance = b["conversation"][0]["utterance"].lower()
            elif "turns" in b:
                benchmark_utterance = b["turns"][0]["utterance"].lower()
            
            overlap = len(input_words.intersection(set(benchmark_utterance.split())))
            if overlap > max_overlap:
                max_overlap = overlap
                best_match = b
        
        if not best_match or max_overlap < 2:
            return {
                "score": 0.0, 
                "benchmark_id": "NONE",
                "feedback": "No relevant benchmark found for deep comparison.",
                "improvement_suggestion": "Expand benchmark library to cover this semantic domain."
            }

        # 2. Extract Ideal Response
        ideal = ""
        if "conversation" in best_match:
            # Get the first teacher turn
            for turn in best_match["conversation"]:
                if turn["role"] == "teacher":
                    ideal = turn.get("ideal_response", "")
                    break
        elif "turns" in best_match:
            ideal = best_match["turns"][1].get("ideal_response", "")

        # 3. Keyword-based Scoring (Task 13.2)
        res_words = set(re.findall(r"\w+", response_text.lower()))
        ideal_words = set(re.findall(r"\w+", ideal.lower()))
        
        # Calculate Jaccard similarity or similar
        intersection = res_words.intersection(ideal_words)
        union = res_words.union(ideal_words)
        score = len(intersection) / len(union) if union else 0.5
        
        # Boost score for structural markers (Task 13.3)
        if any(marker in response_text for marker in ["Method 1", "1.", "Step"]):
             score = min(1.0, score + 0.2)

        return {
            "score": score,
            "benchmark_id": best_match.get("conversation_id", best_match.get("category", "unknown")),
            "ideal_sample": ideal[:100] + "...",
            "improvement_suggestion": "Increase keyword alignment with ideal response structures." if score < 0.6 else "Strong alignment detected."
        }

    def generate_training_scenario(self):
        """Pick a random benchmark to 'teach' the system."""
        if not self.benchmarks: return "No benchmarks loaded."
        target = random.choice(self.benchmarks)
        return target

if __name__ == "__main__":
    # Quick Test
    trainer = ConversationalTrainer("activities/training")
    print(f"Loaded {len(trainer.benchmarks)} benchmarks.")
    result = trainer.evaluate_response("What does 'resilient' mean?", "Resilient means you can recover fast.")
    print(json.dumps(result, indent=2))
