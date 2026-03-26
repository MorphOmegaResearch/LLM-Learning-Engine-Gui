#!/usr/bin/env python3
"""
GAP ANALYZER - Cross-domain understanding gap identification tool
Analyzes text against linguistic hierarchy patterns to identify recognition gaps
"""

import argparse
import json
import re
import sys
import os
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# ============================================================================
# Data Structures
# ============================================================================

class AnalysisLevel(Enum):
    GRAPHOLOGY = "level_1_graphology"
    MORPHOLOGY = "level_2_morphology"
    LEXICAL = "level_3_lexical"
    SYNTAX = "level_4_syntax"
    SEMANTICS = "level_5_semantics"
    PRAGMATICS = "level_6_pragmatics"
    DISCOURSE = "level_7_discourse"
    DOMAIN_ACADEMIC = "domain_academic"
    DOMAIN_TECHNICAL = "domain_technical"
    DOMAIN_INFORMAL = "domain_informal"
    DOMAIN_META = "domain_meta"
    ENTITIES_TEMPORAL = "entities_temporal"
    ENTITIES_NUMERICAL = "entities_numerical"
    ENTITIES_PROPERTIES = "entities_properties"

@dataclass
class PatternResult:
    pattern_name: str
    pattern: str
    level: AnalysisLevel
    matched: bool
    matched_text: List[str]
    reason: str = ""

@dataclass
class GapAnalysis:
    text: str
    recognized_tokens: Set[str]
    unrecognized_tokens: List[str]
    pattern_results: List[PatternResult]
    confidence_score: float
    primary_gaps: List[Tuple[str, str]]  # (token, suggested_pattern)
    recommendations: List[str]

# ============================================================================
# Core Analyzer
# ============================================================================

class GapAnalyzer:
    def __init__(self, patterns_file: str = None, hierarchy_file: str = None):
        """Initialize analyzer with pattern definitions"""
        self.patterns = self._load_patterns(patterns_file)
        self.hierarchy = self._load_hierarchy(hierarchy_file)
        self.baseline_words = self._load_baseline()
        
    def _load_patterns(self, patterns_file: str = None) -> Dict[str, Dict[str, str]]:
        """Load regex patterns from JSON file"""
        if patterns_file and os.path.exists(patterns_file):
            with open(patterns_file, 'r') as f:
                return json.load(f)
        
        # Embedded default patterns (extract from master_regex.json structure)
        return {
            "level_1_graphology": {
                "punctuation": "[.!?]",
                "capitalization_start": "^[A-Z]",
                "proper_noun": "\\b[A-Z][a-z]*\\b"
            },
            "level_2_morphology": {
                "present_participle": "\\w+ing\\b",
                "past_tense": "\\w+ed\\b",
                "plural": "\\w+s\\b",
                "adverbial": "\\w+ly\\b"
            },
            "level_3_lexical": {
                "pronouns": "\\b(I|me|my|mine|you|your|yours|he|him|his|she|her|hers|it|its|we|us|our|ours|they|them|their|theirs)\\b",
                "articles": "\\b(a|an|the)\\b",
                "prepositions": "\\b(in|on|at|by|with|from|to|for|of|about)\\b",
                "question_words": "\\b(what|which|where|who|why|when|how|whose|whom|how many|how much|how often|how long)\\b",
                "modals": "\\b(can|could|will|would|shall|should|may|might|must)\\b"
            },
            "level_4_syntax": {
                "noun_phrase": "\\b(the|a|an)\\s+(\\w+\\s+){0,2}\\w+\\b",
                "verb_phrase": "\\b(am|is|are|was|were|have|has|had|do|does|did|can|will|should)\\s+\\w+ing\\b",
                "interrogative": "\\b(Do|Does|Did|Can|Could|Will|Would|Are|Is|Was|Were|What|Who|Where|When|Why|How)\\s+[\\w\\s]+\\?",
                "imperative": "^\\w+\\s+[\\w\\s]+!|\\b(Don't|Please|Kindly|Let's)\\s+\\w+\\b"
            },
            "level_5_semantics": {
                "causal": "\\b\\w+\\s+(caused|makes|leads to|because|since|as|due to|owing to)\\s+\\w+\\b",
                "volitional": "\\b(I|we)\\s+(want|need|desire|wish|hope|would like|prefer)\\s+[\\w\\s]+\\b"
            },
            "level_6_pragmatics": {
                "greetings": "\\b(hello|hi|hey|good morning|morning|good afternoon|afternoon|good evening|evening)\\b",
                "questions": "\\b(what|who|where|when|why|how|can|could|is|are|do|does|did|will|would)\\s+[\\w\\s]+\\?",
                "affirmations": "\\b(yes|yeah|yep|of course|sure|absolutely|definitely|I agree)\\b"
            },
            "domain_academic": {
                "scholarly": "\\b(furthermore|moreover|nevertheless|consequently|hypothesize|analyze|synthesize|evaluate)\\b",
                "citation": "\\b(et al\\.|ibid\\.|cf\\.|e\\.g\\.|i\\.e\\.)\\b"
            },
            "domain_technical": {
                "hardware": "\\b(CPU|GPU|RAM|SSD|HDD|algorithm|array|boolean|function|variable|class|object)\\b",
                "web": "\\b(API|JSON|XML|HTML|CSS|HTTP|HTTPS|encryption|firewall)\\b"
            },
            "domain_meta": {
                "learning": "\\b(learn|learning|teaching|taught|understand|understanding|unresolved|knowledge gap|epistemic|gap)\\b",
                "correction": "\\b(wrong|actually|incorrect|mistake|error|no it is|not a)\\b"
            }
        }
    
    def _load_hierarchy(self, hierarchy_file: str = None) -> Dict:
        """Load linguistic hierarchy definition"""
        if hierarchy_file and os.path.exists(hierarchy_file):
            with open(hierarchy_file, 'r') as f:
                return json.load(f)
        
        return {
            "language": "English",
            "hierarchy_levels": [
                {"level": 1, "name": "Graphology", "unit": "Characters"},
                {"level": 2, "name": "Morphology", "unit": "Morphemes"},
                {"level": 3, "name": "Lexical", "unit": "Words"},
                {"level": 4, "name": "Syntax", "unit": "Phrases"},
                {"level": 5, "name": "Semantics", "unit": "Propositions"},
                {"level": 6, "name": "Pragmatics", "unit": "Context"},
                {"level": 7, "name": "Discourse", "unit": "Conversation"}
            ]
        }
    
    def _load_baseline(self) -> Set[str]:
        """Load baseline words that should not be considered gaps"""
        return {
            "is", "are", "was", "were", "the", "and", "but", "with", "from", "for",
            "that", "this", "it", "because", "what", "how", "why", "where", "when",
            "who", "which", "can", "could", "will", "would", "shall", "should",
            "may", "might", "must", "have", "has", "had", "do", "does", "did",
            "not", "no", "yes", "ok", "okay", "please", "thank", "thanks", "sorry"
        }
    
    def analyze_text(self, text: str, workflows: List[str] = None) -> GapAnalysis:
        """
        Analyze text for understanding gaps across linguistic domains
        
        Args:
            text: Input text to analyze
            workflows: Specific analysis workflows to run
            
        Returns:
            GapAnalysis object with results
        """
        if not text or not text.strip():
            return GapAnalysis(
                text=text,
                recognized_tokens=set(),
                unrecognized_tokens=[],
                pattern_results=[],
                confidence_score=0.0,
                primary_gaps=[],
                recommendations=["Empty input"]
            )
        
        # Tokenize text
        words = self._tokenize(text)
        
        # Run analysis workflows
        pattern_results = []
        recognized = set()
        
        if workflows is None:
            workflows = ["lexical", "morphology", "syntax", "domain"]
        
        for workflow in workflows:
            results = self._run_workflow(workflow, text, words)
            pattern_results.extend(results)
            
            # Update recognized tokens
            for result in results:
                if result.matched:
                    recognized.update(result.matched_text)
        
        # Identify unrecognized tokens
        unrecognized = []
        for word in words:
            clean_word = word.lower().strip(".,!?;:'\"()[]{}")
            if (clean_word and len(clean_word) > 2 and 
                clean_word not in self.baseline_words and
                clean_word not in recognized):
                unrecognized.append(clean_word)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(words, recognized)
        
        # Identify primary gaps and suggest patterns
        primary_gaps = self._identify_primary_gaps(unrecognized, pattern_results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            unrecognized, primary_gaps, pattern_results, confidence
        )
        
        return GapAnalysis(
            text=text,
            recognized_tokens=recognized,
            unrecognized_tokens=unrecognized,
            pattern_results=pattern_results,
            confidence_score=confidence,
            primary_gaps=primary_gaps,
            recommendations=recommendations
        )
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words"""
        # Remove punctuation and split
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        words = clean_text.lower().split()
        return words
    
    def _run_workflow(self, workflow: str, text: str, words: List[str]) -> List[PatternResult]:
        """Run specific analysis workflow"""
        results = []
        
        if workflow == "lexical":
            results.extend(self._check_lexical(text, words))
        elif workflow == "morphology":
            results.extend(self._check_morphology(text, words))
        elif workflow == "syntax":
            results.extend(self._check_syntax(text))
        elif workflow == "semantics":
            results.extend(self._check_semantics(text))
        elif workflow == "pragmatics":
            results.extend(self._check_pragmatics(text))
        elif workflow == "domain":
            results.extend(self._check_domains(text))
        elif workflow == "all":
            results.extend(self._check_lexical(text, words))
            results.extend(self._check_morphology(text, words))
            results.extend(self._check_syntax(text))
            results.extend(self._check_semantics(text))
            results.extend(self._check_pragmatics(text))
            results.extend(self._check_domains(text))
        
        return results
    
    def _check_lexical(self, text: str, words: List[str]) -> List[PatternResult]:
        """Check lexical patterns"""
        results = []
        level = AnalysisLevel.LEXICAL.value
        
        if level in self.patterns:
            for pattern_name, pattern in self.patterns[level].items():
                matched = False
                matched_text = []
                
                # Check each word
                for word in words:
                    clean_word = word.strip(".,!?;:'\"()[]{}")
                    if re.search(pattern, clean_word, re.IGNORECASE):
                        matched = True
                        matched_text.append(clean_word)
                
                results.append(PatternResult(
                    pattern_name=pattern_name,
                    pattern=pattern,
                    level=AnalysisLevel.LEXICAL,
                    matched=matched,
                    matched_text=matched_text
                ))
        
        return results
    
    def _check_morphology(self, text: str, words: List[str]) -> List[PatternResult]:
        """Check morphological patterns"""
        results = []
        level = AnalysisLevel.MORPHOLOGY.value
        
        if level in self.patterns:
            for pattern_name, pattern in self.patterns[level].items():
                matched = False
                matched_text = []
                
                for word in words:
                    clean_word = word.strip(".,!?;:'\"()[]{}")
                    if re.search(pattern, clean_word, re.IGNORECASE):
                        matched = True
                        matched_text.append(clean_word)
                
                results.append(PatternResult(
                    pattern_name=pattern_name,
                    pattern=pattern,
                    level=AnalysisLevel.MORPHOLOGY,
                    matched=matched,
                    matched_text=matched_text,
                    reason=f"Testing morphology: python3 -c \"import re; print(bool(re.search(r'{pattern}', '{clean_word}')))"
                ))
        
        return results
    
    def _check_syntax(self, text: str) -> List[PatternResult]:
        """Check syntax patterns"""
        results = []
        level = AnalysisLevel.SYNTAX.value
        
        if level in self.patterns:
            for pattern_name, pattern in self.patterns[level].items():
                match = re.search(pattern, text, re.IGNORECASE)
                matched_text = [match.group(0)] if match else []
                
                results.append(PatternResult(
                    pattern_name=pattern_name,
                    pattern=pattern,
                    level=AnalysisLevel.SYNTAX,
                    matched=bool(match),
                    matched_text=matched_text
                ))
        
        return results
    
    def _check_semantics(self, text: str) -> List[PatternResult]:
        """Check semantic patterns"""
        results = []
        level = AnalysisLevel.SEMANTICS.value
        
        if level in self.patterns:
            for pattern_name, pattern in self.patterns[level].items():
                match = re.search(pattern, text, re.IGNORECASE)
                matched_text = [match.group(0)] if match else []
                
                results.append(PatternResult(
                    pattern_name=pattern_name,
                    pattern=pattern,
                    level=AnalysisLevel.SEMANTICS,
                    matched=bool(match),
                    matched_text=matched_text
                ))
        
        return results
    
    def _check_pragmatics(self, text: str) -> List[PatternResult]:
        """Check pragmatic patterns"""
        results = []
        level = AnalysisLevel.PRAGMATICS.value
        
        if level in self.patterns:
            for pattern_name, pattern in self.patterns[level].items():
                match = re.search(pattern, text, re.IGNORECASE)
                matched_text = [match.group(0)] if match else []
                
                results.append(PatternResult(
                    pattern_name=pattern_name,
                    pattern=pattern,
                    level=AnalysisLevel.PRAGMATICS,
                    matched=bool(match),
                    matched_text=matched_text
                ))
        
        return results
    
    def _check_domains(self, text: str) -> List[PatternResult]:
        """Check domain-specific patterns"""
        results = []
        domain_levels = [
            AnalysisLevel.DOMAIN_ACADEMIC,
            AnalysisLevel.DOMAIN_TECHNICAL,
            AnalysisLevel.DOMAIN_INFORMAL,
            AnalysisLevel.DOMAIN_META
        ]
        
        for domain in domain_levels:
            level = domain.value
            if level in self.patterns:
                for pattern_name, pattern in self.patterns[level].items():
                    match = re.search(pattern, text, re.IGNORECASE)
                    matched_text = [match.group(0)] if match else []
                    
                    results.append(PatternResult(
                        pattern_name=pattern_name,
                        pattern=pattern,
                        level=domain,
                        matched=bool(match),
                        matched_text=matched_text
                    ))
        
        return results
    
    def _calculate_confidence(self, words: List[str], recognized: Set[str]) -> float:
        """Calculate confidence score based on recognition rate"""
        if not words:
            return 0.0
        
        # Count recognized content words (non-baseline)
        content_words = [w for w in words 
                        if w.lower() not in self.baseline_words and len(w) > 2]
        
        if not content_words:
            return 1.0  # Only baseline words, high confidence
        
        recognized_content = sum(1 for w in content_words 
                                if w.lower() in recognized)
        
        return recognized_content / len(content_words)
    
    def _identify_primary_gaps(self, 
                              unrecognized: List[str], 
                              pattern_results: List[PatternResult]) -> List[Tuple[str, str]]:
        """Identify primary gaps and suggest patterns"""
        gaps = []
        
        for word in set(unrecognized):  # Deduplicate
            # Try to suggest pattern based on word characteristics
            suggested_pattern = self._suggest_pattern_for_word(word)
            
            if suggested_pattern:
                gaps.append((word, suggested_pattern))
            else:
                gaps.append((word, "unknown"))
        
        return gaps
    
    def _suggest_pattern_for_word(self, word: str) -> str:
        """Suggest regex pattern for an unrecognized word"""
        word_lower = word.lower()
        
        # Check for morphological patterns
        if word_lower.endswith('ing'):
            return r'\w+ing\b'  # Present participle
        elif word_lower.endswith('ed'):
            return r'\w+ed\b'   # Past tense
        elif word_lower.endswith('ly'):
            return r'\w+ly\b'   # Adverb
        elif word_lower.endswith('s') and not word_lower.endswith('ss'):
            return r'\w+s\b'    # Plural or 3rd person singular
        elif re.search(r'[A-Z][a-z]+', word):
            return r'\b[A-Z][a-z]+\b'  # Proper noun
        elif re.search(r'\d', word):
            if re.search(r'\$|£|€|¥', word):
                return r'[\$£€¥]\s?\d+(?:\.\d{2})?'  # Currency
            elif '%' in word:
                return r'\d+\s?%'  # Percentage
            else:
                return r'\b\d+\b'  # Number
        
        return ""
    
    def _generate_recommendations(self,
                                 unrecognized: List[str],
                                 primary_gaps: List[Tuple[str, str]],
                                 pattern_results: List[PatternResult],
                                 confidence: float) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if not unrecognized:
            recommendations.append("All tokens recognized. Confidence is high.")
            return recommendations
        
        # Count gaps by level
        level_gaps = {}
        for gap, pattern in primary_gaps:
            if pattern:
                if pattern == r'\w+ing\b':
                    level_gaps['morphology'] = level_gaps.get('morphology', 0) + 1
                elif pattern == r'\w+ed\b':
                    level_gaps['morphology'] = level_gaps.get('morphology', 0) + 1
                elif pattern.startswith(r'\b[A-Z]'):
                    level_gaps['graphology'] = level_gaps.get('graphology', 0) + 1
                elif pattern.startswith(r'\$') or pattern.startswith(r'\d'):
                    level_gaps['entities'] = level_gaps.get('entities', 0) + 1
        
        # Generate level-specific recommendations
        for level, count in level_gaps.items():
            recommendations.append(
                f"Found {count} {level}-level gaps. Consider adding patterns for {level}."
            )
        
        # General recommendations
        if confidence < 0.5:
            recommendations.append(
                f"Low confidence ({confidence:.2f}). Focus on lexical and morphology patterns."
            )
        
        if len(unrecognized) > 5:
            recommendations.append(
                f"Multiple gaps ({len(unrecognized)}). Consider batch learning or domain-specific patterns."
            )
        
        # Check if missing key patterns
        has_question_words = any(
            r.matched and r.pattern_name == "question_words" 
            for r in pattern_results if r.level == AnalysisLevel.LEXICAL
        )
        
        if not has_question_words and any(w in ['what', 'why', 'how'] for w in unrecognized):
            recommendations.append(
                "Missing question word recognition. Add to lexical patterns."
            )
        
        return recommendations

# ============================================================================
# Workflow Definitions
# ============================================================================

WORKFLOWS = {
    "quick": ["lexical", "morphology"],
    "standard": ["lexical", "morphology", "syntax"],
    "deep": ["lexical", "morphology", "syntax", "semantics", "pragmatics"],
    "domain": ["domain"],
    "full": ["all"],
    "debug": ["lexical", "morphology", "syntax", "semantics", "pragmatics", "domain"]
}

# ============================================================================
# Output Formatters
# ============================================================================

class OutputFormatter:
    @staticmethod
    def format_thought_process(analysis: GapAnalysis) -> str:
        """Format output in thought process style"""
        lines = []
        lines.append("=" * 20 + " THOUGHT PROCESS " + "=" * 20)
        
        # Run through pattern checks
        for result in analysis.pattern_results:
            if result.reason:
                lines.append(f"  * {result.reason}")
            elif not result.matched and "lexical" in result.level.value:
                lines.append(f"  * Testing lexical: python3 -c \"import re;")
                lines.append(f"    print(bool(re.search(r'{result.pattern}', '{result.pattern_name}')))")
                lines.append(f"    Result: FAIL. Token queued for external learning solicitation.")
        
        # Show gaps
        if analysis.unrecognized_tokens:
            lines.append(f"  * Epistemic gaps detected: {analysis.unrecognized_tokens}")
            for gap, pattern in analysis.primary_gaps:
                lines.append(f"  * Gap: '{gap}' -> Suggested pattern: {pattern}")
        
        lines.append("=" * 57)
        return "\n".join(lines)
    
    @staticmethod
    def format_diagnostic(analysis: GapAnalysis) -> str:
        """Format diagnostic output"""
        lines = []
        lines.append("\n[DIAGNOSTIC: GAP ANALYSIS]")
        lines.append(f"Input: {analysis.text}")
        lines.append(f"Confidence Score: {analysis.confidence_score:.2f}")
        lines.append(f"Recognized Tokens: {len(analysis.recognized_tokens)}")
        lines.append(f"Unrecognized Tokens: {len(analysis.unrecognized_tokens)}")
        
        if analysis.unrecognized_tokens:
            lines.append("\nGap Breakdown:")
            for gap, pattern in analysis.primary_gaps:
                lines.append(f"  - '{gap}': {pattern}")
        
        # Pattern summary
        lines.append("\nPattern Recognition:")
        by_level = {}
        for result in analysis.pattern_results:
            level = result.level.value.replace("level_", "").replace("domain_", "")
            if level not in by_level:
                by_level[level] = {"total": 0, "matched": 0}
            by_level[level]["total"] += 1
            if result.matched:
                by_level[level]["matched"] += 1
        
        for level, stats in by_level.items():
            pct = (stats["matched"] / stats["total"] * 100) if stats["total"] > 0 else 0
            lines.append(f"  {level}: {stats['matched']}/{stats['total']} ({pct:.1f}%)")
        
        lines.append("-" * 30)
        return "\n".join(lines)
    
    @staticmethod
    def format_json(analysis: GapAnalysis) -> str:
        """Format as JSON"""
        import json as json_module
        data = {
            "text": analysis.text,
            "confidence": analysis.confidence_score,
            "recognized_tokens": list(analysis.recognized_tokens),
            "unrecognized_tokens": analysis.unrecognized_tokens,
            "primary_gaps": [{"token": g[0], "suggested_pattern": g[1]} 
                           for g in analysis.primary_gaps],
            "recommendations": analysis.recommendations,
            "pattern_summary": {
                result.pattern_name: {
                    "level": result.level.value,
                    "matched": result.matched,
                    "matches": result.matched_text
                }
                for result in analysis.pattern_results
            }
        }
        return json_module.dumps(data, indent=2)
    
    @staticmethod
    def format_commands(analysis: GapAnalysis) -> str:
        """Format as executable commands for testing"""
        lines = []
        lines.append("\n[COMMANDS FOR MANUAL TESTING]")
        
        for gap, pattern in analysis.primary_gaps:
            if pattern and pattern != "unknown":
                cmd = f"python3 -c \"import re; print(bool(re.search(r'{pattern}', '{gap}')))"
                lines.append(f"# Test '{gap}' against pattern '{pattern}':")
                lines.append(cmd + '"')
                lines.append("")
        
        # Generate pattern addition commands
        if analysis.unrecognized_tokens:
            lines.append("\n[SUGGESTED PATTERN ADDITIONS]")
            lines.append("# Add to master_regex.json under appropriate level:")
            for gap, pattern in analysis.primary_gaps:
                if pattern and pattern != "unknown":
                    lines.append(f"# '{gap}': \"{pattern}\",")
        
        return "\n".join(lines)

# ============================================================================
# Main CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GAP ANALYZER - Cross-domain understanding gap identification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "because the system is slow"
  %(prog)s "why is CPU temperature high?" --workflow deep
  %(prog)s "what is quantum tunneling?" --format diagnostic
  %(prog)s "professional development costs $500" --output commands
        """
    )
    
    # Main arguments
    parser.add_argument("text", nargs="?", help="Text to analyze for gaps")
    parser.add_argument("--file", "-f", help="Read text from file")
    
    # Analysis options
    parser.add_argument("--workflow", "-w", 
                       choices=list(WORKFLOWS.keys()),
                       default="standard",
                       help="Analysis workflow (default: standard)")
    
    parser.add_argument("--format", "-fmt",
                       choices=["thought", "diagnostic", "json", "commands", "all"],
                       default="thought",
                       help="Output format (default: thought)")
    
    parser.add_argument("--patterns", "-p",
                       help="Custom patterns JSON file")
    
    parser.add_argument("--hierarchy", "-H",
                       help="Custom hierarchy JSON file")
    
    parser.add_argument("--verbose", "-v",
                       action="store_true",
                       help="Verbose output with all pattern results")
    
    parser.add_argument("--test", "-t",
                       action="store_true",
                       help="Run test suite")
    
    parser.add_argument("--interactive", "-i",
                       action="store_true",
                       help="Interactive mode")
    
    args = parser.parse_args()
    
    # Handle test mode
    if args.test:
        run_tests()
        return
    
    # Handle interactive mode
    if args.interactive:
        run_interactive(args)
        return
    
    # Get input text
    text = args.text
    if args.file:
        try:
            with open(args.file, 'r') as f:
                text = f.read().strip()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}")
            return 1
    
    if not text and not args.interactive:
        parser.print_help()
        print("\nError: No text provided. Use --file or provide text as argument.")
        return 1
    
    # Run analysis
    analyzer = GapAnalyzer(args.patterns, args.hierarchy)
    analysis = analyzer.analyze_text(text, WORKFLOWS[args.workflow])
    
    # Output results
    if args.format == "thought" or args.format == "all":
        print(OutputFormatter.format_thought_process(analysis))
    
    if args.format == "diagnostic" or args.format == "all":
        print(OutputFormatter.format_diagnostic(analysis))
    
    if args.format == "json" or args.format == "all":
        print(OutputFormatter.format_json(analysis))
    
    if args.format == "commands" or args.format == "all":
        print(OutputFormatter.format_commands(analysis))
    
    # Verbose output
    if args.verbose:
        print("\n[VERBOSE: PATTERN RESULTS]")
        for result in analysis.pattern_results:
            status = "✓" if result.matched else "✗"
            print(f"  {status} {result.level.value}.{result.pattern_name}: "
                  f"{result.matched_text if result.matched else 'No match'}")
    
    # Show recommendations
    if analysis.recommendations:
        print("\n[RECOMMENDATIONS]")
        for rec in analysis.recommendations:
            print(f"  • {rec}")

def run_interactive(args):
    """Run in interactive mode"""
    print("GAP ANALYZER - Interactive Mode")
    print("Type 'quit' or 'exit' to end\n")
    
    analyzer = GapAnalyzer(args.patterns, args.hierarchy)
    
    while True:
        try:
            text = input("Enter text to analyze: ").strip()
            if text.lower() in ['quit', 'exit', 'q']:
                break
            
            if not text:
                continue
            
            analysis = analyzer.analyze_text(text, WORKFLOWS[args.workflow])
            print(OutputFormatter.format_thought_process(analysis))
            print(OutputFormatter.format_diagnostic(analysis))
            
            if analysis.recommendations:
                print("\n[RECOMMENDATIONS]")
                for rec in analysis.recommendations:
                    print(f"  • {rec}")
            
            print("\n" + "="*60 + "\n")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

def run_tests():
    """Run test suite"""
    test_cases = [
        "because the system is slow",
        "why is CPU temperature high?",
        "what is quantum tunneling?",
        "professional development costs $500",
        "I want to learn machine learning algorithms",
        "The database connection timeout after 30 seconds"
    ]
    
    analyzer = GapAnalyzer()
    
    print("RUNNING TEST SUITE...\n")
    for test in test_cases:
        print(f"Testing: {test}")
        analysis = analyzer.analyze_text(test, WORKFLOWS["debug"])
        print(f"  Confidence: {analysis.confidence_score:.2f}")
        print(f"  Gaps: {len(analysis.unrecognized_tokens)}")
        if analysis.unrecognized_tokens:
            print(f"  Unrecognized: {analysis.unrecognized_tokens}")
        print()

# ============================================================================
# Direct Python Execution Helper
# ============================================================================

def quick_analyze(text: str) -> str:
    """Quick analysis function for inline use"""
    analyzer = GapAnalyzer()
    analysis = analyzer.analyze_text(text, ["lexical", "morphology"])
    
    output = []
    output.append(f"Text: {text}")
    output.append(f"Confidence: {analysis.confidence_score:.2f}")
    
    if analysis.unrecognized_tokens:
        output.append(f"Gaps: {analysis.unrecognized_tokens}")
        for gap, pattern in analysis.primary_gaps:
            if pattern:
                output.append(f"  '{gap}' -> try pattern: {pattern}")
    
    return "\n".join(output)

# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    # Example direct usage:
    # python3 -c "from gap_analyzer import quick_analyze; print(quick_analyze('because it is professional'))"
    
    # Or as script:
    # python gap_analyzer.py "because it is professional" --workflow deep --format all
    
    main()