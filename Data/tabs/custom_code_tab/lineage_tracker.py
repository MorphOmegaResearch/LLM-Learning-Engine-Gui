"""
Lineage Tracker - Track model training lineage and parent-child relationships
Simple module with no external dependencies beyond standard library
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class LineageTracker:
    """Tracks model lineage - which models were trained from which base models"""

    def __init__(self, lineage_dir: Optional[Path] = None):
        """
        Initialize the lineage tracker

        Args:
            lineage_dir: Directory to store lineage data. If None, uses default Training_Data-Sets/Lineage
        """
        if lineage_dir is None:
            # Default to Training_Data-Sets/Lineage directory
            self.lineage_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Lineage"
        else:
            self.lineage_dir = Path(lineage_dir)

        # Ensure lineage directory exists
        self.lineage_dir.mkdir(parents=True, exist_ok=True)

        # Lineage file (stores all lineage records)
        self.lineage_file = self.lineage_dir / "model_lineage.jsonl"

        # Index file (for quick lookups)
        self.index_file = self.lineage_dir / "lineage_index.json"

        # In-memory cache
        self._index_cache = None

    def record_training(
        self,
        model_name: str,
        base_model: str,
        training_date: Optional[str] = None,
        training_data_source: Optional[str] = None,
        training_method: str = "fine-tune",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record that a model was trained from a base model

        Args:
            model_name: Name of the newly trained model
            base_model: Name of the base/parent model
            training_date: ISO format date (defaults to now)
            training_data_source: Path or description of training data
            training_method: Method used (fine-tune, merge, distill, etc.)
            metadata: Additional metadata (epochs, learning rate, etc.)

        Returns:
            True if recorded successfully, False otherwise
        """
        try:
            if training_date is None:
                training_date = datetime.now().isoformat()

            lineage_entry = {
                "model_name": model_name,
                "base_model": base_model,
                "training_date": training_date,
                "training_data_source": training_data_source,
                "training_method": training_method,
                "metadata": metadata or {},
                "recorded_at": datetime.now().isoformat()
            }

            # Append to lineage file
            with open(self.lineage_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(lineage_entry) + '\n')

            # Update index
            self._update_index(model_name, base_model)

            return True

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to record training: {e}")
            return False

    def record_morph_interaction(
        self,
        variant_sha: str,
        control_signal: str,
        prompt: str,
        response: str,
        accepted: bool,
        gap_severity: str = "LOW",
        task_ids: List[str] = None,
        sampling_params: Dict[str, Any] = None,
    ) -> bool:
        """
        Record a Morph inference interaction for the K5 training loop.

        Records go to model_lineage.jsonl (record_type="morph_interaction") and
        also to Training_Data-Sets/morph_evals/ as JSONL tuples for LoRA fine-tuning.
        """
        try:
            record = {
                "record_type":     "morph_interaction",
                "variant_sha":     variant_sha,
                "control_signal":  control_signal,
                "prompt":          prompt,
                "response":        response,
                "accepted":        accepted,
                "gap_severity":    gap_severity,
                "task_ids":        task_ids or [],
                "sampling_params": sampling_params or {},
                "recorded_at":     datetime.now().isoformat(),
            }
            # Append to model_lineage.jsonl
            with open(self.lineage_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

            # Also write to morph_evals/ for K5 fine-tune pipeline
            morph_evals_dir = self.lineage_dir.parent / "morph_evals"
            morph_evals_dir.mkdir(parents=True, exist_ok=True)
            suffix = "accepted" if accepted else "rejected"
            eval_file = morph_evals_dir / f"{suffix}_{datetime.now().strftime('%Y%m%d')}.jsonl"
            eval_record = {
                "prompt":         prompt,
                "response":       response,
                "accepted":       accepted,
                "variant_sha":    variant_sha,
                "control_signal": control_signal,
                "gap_severity":   gap_severity,
                "task_ids":       task_ids or [],
                "recorded_at":    record["recorded_at"],
            }
            with open(eval_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(eval_record, ensure_ascii=False) + '\n')

            return True

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to record morph interaction: {e}")
            return False

    def get_morph_interactions(
        self,
        variant_sha: str = None,
        accepted_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Return morph interaction records from model_lineage.jsonl.

        Args:
            variant_sha: If given, filter to records with this sha.
            accepted_only: If True, return only accepted=True records.
        """
        results = []
        if not self.lineage_file.exists():
            return results
        try:
            with open(self.lineage_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("record_type") != "morph_interaction":
                        continue
                    if variant_sha and rec.get("variant_sha") != variant_sha:
                        continue
                    if accepted_only and not rec.get("accepted", False):
                        continue
                    results.append(rec)
        except Exception as e:
            print(f"LineageTracker ERROR: Failed to read morph interactions: {e}")
        return results

    def get_lineage_chain(self, model_name: str) -> List[Dict[str, Any]]:
        """
        Get the full lineage chain for a model (all ancestors)

        Args:
            model_name: Name of the model

        Returns:
            List of lineage records from oldest ancestor to the model itself
            Each record contains: model_name, base_model, training_date, etc.
        """
        chain = []
        current_model = model_name
        visited = set()  # Prevent infinite loops

        while current_model and current_model not in visited:
            visited.add(current_model)

            # Get lineage record for current model
            record = self.get_lineage_record(current_model)

            if not record:
                break

            chain.insert(0, record)  # Insert at beginning to build oldest->newest
            current_model = record.get("base_model")

        return chain

    def get_lineage_record(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the lineage record for a specific model

        Args:
            model_name: Name of the model

        Returns:
            Lineage record dict or None if not found
        """
        if not self.lineage_file.exists():
            return None

        try:
            # Search lineage file for the model (most recent record)
            latest_record = None

            with open(self.lineage_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        if entry.get("model_name") == model_name:
                            latest_record = entry
                    except json.JSONDecodeError:
                        continue

            return latest_record

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to get lineage record: {e}")
            return None

    def get_children(self, base_model: str) -> List[str]:
        """
        Get all models that were trained from a specific base model

        Args:
            base_model: Name of the base model

        Returns:
            List of model names trained from this base
        """
        if not self.lineage_file.exists():
            return []

        children = set()

        try:
            with open(self.lineage_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        if entry.get("base_model") == base_model:
                            children.add(entry.get("model_name"))
                    except json.JSONDecodeError:
                        continue

            return sorted(list(children))

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to get children: {e}")
            return []

    def get_lineage_tree(self, root_model: str, max_depth: int = 5) -> Dict[str, Any]:
        """
        Get a tree structure of all descendants from a root model

        Args:
            root_model: The root model to start from
            max_depth: Maximum depth to traverse

        Returns:
            Nested dict representing the lineage tree:
            {
                "model": "root_model",
                "children": [
                    {"model": "child1", "children": [...]},
                    {"model": "child2", "children": [...]}
                ]
            }
        """
        def build_tree(model: str, depth: int = 0) -> Dict[str, Any]:
            if depth >= max_depth:
                return {"model": model, "children": [], "truncated": True}

            children = self.get_children(model)
            child_trees = [build_tree(child, depth + 1) for child in children]

            return {
                "model": model,
                "children": child_trees,
                "child_count": len(children)
            }

        return build_tree(root_model)

    def get_all_lineages(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all lineage records grouped by model

        Returns:
            Dict mapping model names to their lineage records
        """
        lineages = {}

        if not self.lineage_file.exists():
            return lineages

        try:
            with open(self.lineage_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        model_name = entry.get("model_name")

                        if model_name not in lineages:
                            lineages[model_name] = []

                        lineages[model_name].append(entry)
                    except json.JSONDecodeError:
                        continue

            # Sort each model's records by date (most recent first)
            for model_name in lineages:
                lineages[model_name].sort(
                    key=lambda x: x.get("training_date", ""),
                    reverse=True
                )

            return lineages

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to get all lineages: {e}")
            return {}

    def get_root_models(self) -> List[str]:
        """
        Get all models that have no parent (root models)

        Returns:
            List of root model names
        """
        if not self.lineage_file.exists():
            return []

        all_models = set()
        child_models = set()

        try:
            with open(self.lineage_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        model_name = entry.get("model_name")
                        base_model = entry.get("base_model")

                        all_models.add(model_name)
                        child_models.add(model_name)

                        if base_model:
                            all_models.add(base_model)

                    except json.JSONDecodeError:
                        continue

            # Root models are those that appear as base_model but not as model_name
            root_models = all_models - child_models

            return sorted(list(root_models))

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to get root models: {e}")
            return []

    def has_lineage(self, model_name: str) -> bool:
        """Check if a model has any lineage records"""
        return self.get_lineage_record(model_name) is not None

    def get_training_method_summary(self) -> Dict[str, int]:
        """
        Get summary of training methods used across all models

        Returns:
            Dict mapping training method to count
        """
        summary = {}

        if not self.lineage_file.exists():
            return summary

        try:
            with open(self.lineage_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        method = entry.get("training_method", "unknown")
                        summary[method] = summary.get(method, 0) + 1
                    except json.JSONDecodeError:
                        continue

            return summary

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to get method summary: {e}")
            return {}

    def clear_lineage(self, model_name: Optional[str] = None) -> bool:
        """
        Clear lineage data

        Args:
            model_name: If provided, clear only this model's lineage.
                       If None, clear all lineage data.

        Returns:
            True if cleared successfully
        """
        try:
            if model_name is None:
                # Clear all data
                if self.lineage_file.exists():
                    self.lineage_file.unlink()
                if self.index_file.exists():
                    self.index_file.unlink()
                self._index_cache = None
                return True
            else:
                # Remove specific model's entries
                if not self.lineage_file.exists():
                    return True

                # Read all entries except the target model
                entries = []
                with open(self.lineage_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get("model_name") != model_name:
                                entries.append(entry)
                        except json.JSONDecodeError:
                            continue

                # Rewrite file without the target model
                with open(self.lineage_file, 'w', encoding='utf-8') as f:
                    for entry in entries:
                        f.write(json.dumps(entry) + '\n')

                # Rebuild index
                self._rebuild_index()
                return True

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to clear lineage: {e}")
            return False

    def _update_index(self, model_name: str, base_model: str):
        """Update the index with a new lineage entry"""
        try:
            # Load existing index
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    index = json.load(f)
            else:
                index = {}

            # Update index
            index[model_name] = {
                "base_model": base_model,
                "last_updated": datetime.now().isoformat()
            }

            # Save index
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)

            # Update cache
            self._index_cache = index

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to update index: {e}")

    def _rebuild_index(self):
        """Rebuild the index from the lineage file"""
        try:
            if not self.lineage_file.exists():
                return

            index = {}

            with open(self.lineage_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        model_name = entry.get("model_name")
                        base_model = entry.get("base_model")

                        if model_name:
                            index[model_name] = {
                                "base_model": base_model,
                                "last_updated": entry.get("training_date", "")
                            }
                    except json.JSONDecodeError:
                        continue

            # Save index
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)

            # Update cache
            self._index_cache = index

        except Exception as e:
            print(f"LineageTracker ERROR: Failed to rebuild index: {e}")


# Convenience singleton instance
_global_tracker = None


def get_tracker(lineage_dir: Optional[Path] = None) -> LineageTracker:
    """Get the global tracker instance (singleton pattern)"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = LineageTracker(lineage_dir)
    return _global_tracker
