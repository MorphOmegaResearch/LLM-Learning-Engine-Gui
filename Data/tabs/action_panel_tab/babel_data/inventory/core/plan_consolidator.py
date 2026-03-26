#!/usr/bin/env python3
"""
Plan Consolidator - Discover, catalog, and organize scattered plan files
Part of Babel v01a Project Intelligence Layer

Author: Babel Team
Created: 2026-02-10
"""

import json
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

# Setup logging
logger = logging.getLogger("plan_consolidator")


class PlanConsolidator:
    """Discover, catalog, and organize scattered plan files using Filesync + taxonomy"""

    def __init__(self, babel_root: Path):
        self.babel_root = Path(babel_root)
        # When babel_root=Trainer/, plans live at Data/plans/ not plans/
        _data_plans = self.babel_root / "Data" / "plans"
        self.plans_dir = _data_plans if _data_plans.exists() else self.babel_root / "plans"
        self.taxonomy_path = self.babel_root / "Data/tabs/action_panel_tab/babel_data/profile/schemas/universal_taxonomy.json"
        self.regex_path = self.babel_root / "Data/tabs/action_panel_tab/babel_data/profile/schemas/master_regex.json"

        # Exclusion patterns — must be broad enough to skip package dirs when scanning Trainer/
        self.exclude_dirs = [
            "babel_data",
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            "backup",           # 5800+ backup dirs
            "history",          # per-file backup history
            "site-packages",    # Python package READMEs
            "Provisions",       # bundled .whl packages
            "variants",         # omega/alpha generated scripts
            "forekit_data",     # session/manifest data
            ".claude",          # Claude CLI plans
            ".gemini",          # Gemini CLI data
            "vendor",
            "dist-packages",
        ]

        self.exclude_files = [
            "README.md",
            "CHANGELOG.md",
            "Project_Template_1.md",
            "PROGRESS_T30.md",
        ]

    def discover_scattered_plans(self) -> List[Dict]:
        """Find all .md files in /Babel_v01a (excluding known locations)

        #TODO Visual Check: Plan discovery loop starts here

        Returns:
            List of plan info dicts with: path, name, size, mtime, location
        """
        # Cache with 10-minute staleness to avoid rglob on every latest run
        _cache_path = self.babel_root / "babel_data" / "plan_discovery_cache.json"
        if _cache_path.exists():
            try:
                _cache = json.loads(_cache_path.read_text(encoding="utf-8"))
                _age = (datetime.now() - datetime.fromisoformat(_cache["generated"])).total_seconds()
                if _age < 600:  # 10 minutes
                    logger.info(f"[PLAN DISCOVERY] Using cache ({_age:.0f}s old)")
                    return _cache["plans"]
            except Exception:
                pass

        scattered_plans = []

        logger.info(f"[PLAN DISCOVERY] Scanning {self.babel_root}")

        # Recursive search for .md files
        for md_file in self.babel_root.rglob("*.md"):
            # Skip excluded directories
            if any(excl in str(md_file) for excl in self.exclude_dirs):
                continue

            # Skip known root files
            if md_file.name in self.exclude_files and md_file.parent == self.babel_root:
                continue

            # Skip if already in plans/
            if md_file.parent == self.plans_dir:
                continue

            # Skip if in plans/ subdirectories (already organized)
            if self.plans_dir in md_file.parents:
                continue

            # Found scattered plan!
            try:
                stat_info = md_file.stat()
                plan_info = {
                    "path": str(md_file),
                    "name": md_file.name,
                    "size": stat_info.st_size,
                    "mtime": stat_info.st_mtime,
                    "mtime_iso": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    "location": str(md_file.relative_to(self.babel_root))
                }
                scattered_plans.append(plan_info)
                logger.info(f"  Found: {plan_info['location']}")
            except Exception as e:
                logger.error(f"  Error processing {md_file}: {e}")

        logger.info(f"[PLAN DISCOVERY] Found {len(scattered_plans)} scattered .md files")

        # Write cache
        try:
            _cache_path.parent.mkdir(parents=True, exist_ok=True)
            _cache_path.write_text(json.dumps({
                "generated": datetime.now().isoformat(),
                "plans": scattered_plans
            }, indent=2), encoding="utf-8")
        except Exception:
            pass

        return scattered_plans

    def analyze_plan_with_filesync(self, plan_path: Path) -> Dict:
        """Use Filesync to get timeline context for plan file

        #TODO Visual Check: Filesync subprocess call

        Args:
            plan_path: Path to plan file

        Returns:
            Timeline context dict with: first_seen, last_modified, cluster_id, related_files
        """
        logger.info(f"[FILESYNC ANALYSIS] Analyzing {plan_path.name}")

        try:
            # Use history_temporal_manifest directly (faster + more reliable than subprocess)
            timeline_dir = self.babel_root / "babel_data/timeline/manifests"
            htm_path = timeline_dir / "history_temporal_manifest.json"
            filesync_data = self._get_fallback_timeline_data(plan_path)

            if htm_path.exists():
                htm = json.loads(htm_path.read_text(encoding="utf-8"))
                _stem = plan_path.stem.lower()
                for _hname, _hprof in htm.get("profiles", {}).items():
                    if _stem in _hname.lower():
                        filesync_data["cluster_id"] = f"hist_{_hname[:30]}"
                        filesync_data["first_seen"] = _hprof.get("first_seen")
                        filesync_data["last_modified"] = _hprof.get("last_seen")
                        filesync_data["backup_count"] = _hprof.get("backup_count", 0)
                        filesync_data["activity_score"] = _hprof.get("activity_score", 0)
                        break

            # Also check timeline manifests for additional context
            cluster_id = self._find_cluster_in_manifests(plan_path, timeline_dir)
            if cluster_id:
                filesync_data["cluster_id"] = cluster_id

            logger.info(f"  Cluster: {filesync_data.get('cluster_id', 'unknown')}")
            return filesync_data

        except Exception as e:
            logger.error(f"  Filesync analysis error: {e}")
            return self._get_fallback_timeline_data(plan_path)

    def _parse_filesync_output(self, output: str) -> Dict:
        """Parse Filesync command output"""
        data = {
            "first_seen": None,
            "last_modified": None,
            "cluster_id": None,
            "related_files": []
        }

        # Extract timestamps and cluster info
        # (This is simplified - actual Filesync output format may vary)
        for line in output.split('\n'):
            if "First seen:" in line:
                data["first_seen"] = line.split(":", 1)[1].strip()
            elif "Last modified:" in line:
                data["last_modified"] = line.split(":", 1)[1].strip()
            elif "Cluster:" in line:
                data["cluster_id"] = line.split(":", 1)[1].strip()
            elif "Related:" in line:
                # Parse related files list
                files_str = line.split(":", 1)[1].strip()
                data["related_files"] = [f.strip() for f in files_str.split(",")]

        return data

    def _find_cluster_in_manifests(self, plan_path: Path, timeline_dir: Path) -> Optional[str]:
        """Search timeline manifests for cluster association"""
        if not timeline_dir.exists():
            return None

        plan_name = plan_path.name

        # Search recent manifests
        manifests = sorted(timeline_dir.glob("manifest_*.json"),
                          key=lambda p: p.stat().st_mtime,
                          reverse=True)[:10]  # Check last 10

        for manifest_path in manifests:
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)

                # Check if this plan is mentioned
                if "files" in manifest:
                    for file_entry in manifest["files"]:
                        if plan_name in file_entry.get("path", ""):
                            # Found it! Extract cluster if present
                            return file_entry.get("cluster_id", manifest_path.stem)
            except Exception:
                continue

        return None

    def _get_fallback_timeline_data(self, plan_path: Path) -> Dict:
        """Generate timeline data from file metadata if Filesync fails"""
        stat_info = plan_path.stat()
        mtime = datetime.fromtimestamp(stat_info.st_mtime)

        # Generate cluster ID from timestamp
        cluster_id = f"unclustered_{mtime.strftime('%Y%m%d_%H')}"

        return {
            "first_seen": mtime.isoformat(),
            "last_modified": mtime.isoformat(),
            "cluster_id": cluster_id,
            "related_files": []
        }

    def classify_plan_type(self, plan_path: Path, use_morph: bool = False) -> str:
        """Classify plan into project type using Os_Toolkit taxonomy

        #TODO Visual Check: Taxonomy loading logic

        Args:
            plan_path: Path to plan file
            use_morph: Whether to use Morph regex validation

        Returns:
            Project type string (e.g., "Feature_Development")
        """
        logger.info(f"[TYPE CLASSIFICATION] Classifying {plan_path.name}")

        # Read plan content
        try:
            with open(plan_path, encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
        except Exception as e:
            logger.error(f"  Error reading plan: {e}")
            return "Unknown_Project"

        # Load taxonomy (if available)
        taxonomy = self._load_taxonomy()

        # Define project types with keywords
        project_types = {
            "Feature_Development": ["feature", "implement", "add", "create", "build", "develop"],
            "Debug_Project": ["bug", "fix", "error", "issue", "crash", "debug", "resolve"],
            "Refactor_Project": ["refactor", "cleanup", "reorganize", "optimize", "improve"],
            "Research_Project": ["explore", "investigate", "research", "understand", "analyze", "study"],
            "Integration_Project": ["integrate", "connect", "link", "sync", "unify", "coordinate"],
            "Documentation_Project": ["document", "explain", "guide", "tutorial", "readme", "manual"],
            "Testing_Project": ["test", "verify", "validate", "benchmark", "qa"],
            "UX_Project": ["ux", "ui", "interface", "design", "layout", "visual"]
        }

        # Score each type
        scores = {}
        for proj_type, keywords in project_types.items():
            score = 0
            for keyword in keywords:
                # Count occurrences
                count = content.count(keyword)
                # Weight by position (keywords in title/header are more important)
                if keyword in content[:200]:  # First 200 chars
                    score += count * 2
                else:
                    score += count
            scores[proj_type] = score

        # Get best match
        if max(scores.values()) == 0:
            best_type = "Minimal_Project"
        else:
            best_type = max(scores.items(), key=lambda x: x[1])[0]

        logger.info(f"  Type: {best_type} (score: {scores[best_type]})")

        # Optional: Validate with Morph regex
        if use_morph:
            morph_result = self._validate_with_morph_regex(content, best_type)
            if morph_result["confidence"] < 0.5:
                logger.warning(f"  ⚠️ Morph validation conflict: {best_type} vs {morph_result['suggested_type']}")
                # Log event for debugging
                # #[Event:MORPH_VALIDATE]

        return best_type

    def _load_taxonomy(self) -> Dict:
        """Load Os_Toolkit universal taxonomy"""
        try:
            if self.taxonomy_path.exists():
                with open(self.taxonomy_path) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load taxonomy: {e}")

        return {}

    def _validate_with_morph_regex(self, content: str, proposed_type: str) -> Dict:
        """Use Morph regex patterns to validate classification (CAUTIOUSLY)

        #TODO SAFE: regex only, NO sequence logic

        Args:
            content: Plan file content
            proposed_type: Type suggested by Os_Toolkit taxonomy

        Returns:
            Validation dict with confidence and suggested_type
        """
        # Check if Morph patterns exist
        morph_regex_path = self.babel_root / "babel_data/inventory/action_panel/morph/regex_project/patterns.json"

        if not morph_regex_path.exists():
            # No Morph available - trust Os_Toolkit
            return {
                "confidence": 1.0,
                "suggested_type": proposed_type,
                "pattern_matches": {}
            }

        try:
            with open(morph_regex_path) as f:
                morph_patterns = json.load(f)

            # Run ONLY regex matching (NOT Morph's sequence logic!)
            pattern_matches = {}
            for pattern_name, pattern_regex in morph_patterns.items():
                try:
                    matches = re.findall(pattern_regex, content, re.IGNORECASE)
                    pattern_matches[pattern_name] = len(matches)
                except re.error:
                    continue

            # Simple validation: if patterns match proposed type, high confidence
            # This is VERY simplified - avoid Morph's complex logic
            confidence = 0.8  # Default moderate confidence

            return {
                "confidence": confidence,
                "suggested_type": proposed_type,
                "pattern_matches": pattern_matches
            }

        except Exception as e:
            logger.error(f"Morph validation error: {e}")
            return {
                "confidence": 1.0,
                "suggested_type": proposed_type,
                "pattern_matches": {}
            }

    def organize_plan(self, plan_path: Path, project_type: str, filesync_data: Dict) -> Optional[Path]:
        """Move plan to correct location and update metadata

        Args:
            plan_path: Current path to plan
            project_type: Classified project type
            filesync_data: Timeline context from Filesync

        Returns:
            New path if successful, None otherwise
        """
        # Create type-based subdirectory
        type_dir = self.plans_dir / project_type.lower()
        type_dir.mkdir(parents=True, exist_ok=True)

        # Determine final filename
        timestamp = filesync_data.get("first_seen", "unknown")
        if isinstance(timestamp, str) and "T" in timestamp:
            timestamp = timestamp.split("T")[0].replace("-", "")

        cluster = filesync_data.get("cluster_id", "unclustered")
        if cluster:
            cluster = cluster.replace("/", "_").replace(" ", "_")[:30]

        original_name = plan_path.stem

        # New filename format: {timestamp}_{cluster}_{original_name}.md
        new_name = f"{timestamp}_{cluster}_{original_name}.md"
        new_path = type_dir / new_name

        # Check if already exists
        if new_path.exists():
            logger.warning(f"  Target already exists: {new_path}")
            return None

        try:
            # Copy file (preserve timestamps)
            shutil.copy2(plan_path, new_path)
            logger.info(f"  Organized: {plan_path.name} → {new_path.relative_to(self.babel_root)}")

            # Archive original (don't delete immediately)
            archive_dir = self.babel_root / "babel_data/archive/plans"
            archive_dir.mkdir(parents=True, exist_ok=True)

            archive_path = archive_dir / plan_path.name
            if not archive_path.exists():
                shutil.move(plan_path, archive_path)
                logger.info(f"  Archived: {plan_path.name}")
            else:
                # If archive exists, just delete original
                plan_path.unlink()
                logger.info(f"  Removed: {plan_path.name}")

            return new_path

        except Exception as e:
            logger.error(f"  Error organizing plan: {e}")
            return None


def main():
    """Test PlanConsolidator"""
    babel_root = Path(__file__).parent.parent.parent.parent

    consolidator = PlanConsolidator(babel_root)

    # Discover scattered plans
    scattered = consolidator.discover_scattered_plans()

    print(f"\n[PLAN CONSOLIDATION TEST]")
    print(f"Found {len(scattered)} scattered .md files:\n")

    for plan_info in scattered[:10]:  # Show first 10
        print(f"  - {plan_info['location']} ({plan_info['size']} bytes)")

    if len(scattered) > 10:
        print(f"  ... and {len(scattered) - 10} more")


if __name__ == "__main__":
    main()
