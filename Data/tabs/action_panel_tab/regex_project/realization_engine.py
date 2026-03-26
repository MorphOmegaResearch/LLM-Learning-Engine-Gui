import json
import random
import os

class RealizationEngine:
    """
    Translates Logical Intent and 5W1H into a natural language response.
    Uses Level-based constraints to ensure grammatical and contextual accuracy.
    """

    def __init__(self, strategies_path, academia_path=None):
        with open(strategies_path, 'r') as f:
            self.strategies = json.load(f)
        
        self.academia = {}
        if academia_path and os.path.exists(academia_path):
            with open(academia_path, 'r') as f:
                self.academia = json.load(f)

    def realize(self, resolved_intent, active_domain="general", active_persona="Assistant", memory_match=None, properties={}, willingness=0.5, mode="EXPLORATORY", interaction_type="GENERAL_EXCHANGE", curiosity_level=0.0, recent_thoughts=[], sequence_completed=False, boredom_score=0.0, suggested_activity=None, routine_match=None, output_cadence="medium", volition_score=0.0, calibration_active=False): #[Mark:REALIZE_CORE]
        """
        Synthesizes a response from the resolved interaction object using a Context Vector.
        Returns (response_text, path_id)
        """
        signals = resolved_intent.get("system_signals", {})
        situation = resolved_intent.get("active_situation")
        intent = resolved_intent.get("logical_intent")
        five_ws = resolved_intent.get("5w1h_resolution")
        what = five_ws.get("what")
        hierarchy = resolved_intent.get("hierarchy_analysis", {})
        
        # 0. Context Vector Synthesis (Task: Variable Matrix)
        context_vector = self._calculate_context_vector(routine_match, signals, interaction_type, boredom_score)
        
        path_id = f"{intent}_{active_domain}_{active_persona}_{output_cadence}"
        
        # 1. Persona and Situational Prefix
        persona_prefix = f"[{active_persona} Mode] "
        if situation:
            persona_prefix += f"<{situation}> "
        
        # Apply Matrix Toggles to Prefix
        if context_vector["formality"] == "high":
            persona_prefix = persona_prefix.replace("[", "[Formal ").replace("Mode]", "Protocol]")
        elif context_vector["energy"] == "low":
            persona_prefix = persona_prefix.replace("]", " Reflective]")

        # 1.3 Calibration Follow-up (Task: ask why to further resolve gradient)
        calib_hook = ""
        if calibration_active:
            calib_hook = f" Why is this specific alignment better for our current {situation or 'general'} context?"

        sentiment_prefix = ""
        # ... rest of prefixes ...

        # 1.4 Routine Acknowledgment (Task 11.4)
        routine_hook = ""
        if routine_match and random.random() > 0.5:
            routine_hook = f"(Acknowledging our {routine_match['activity']} slot)... "

        # 1.5 Thought Reminder (Task 5.3) - Internal continuity
        thought_hook = ""
        if len(recent_thoughts) > 2 and random.random() > 0.7:
            prev_thought = recent_thoughts[-3]
            if prev_thought != "GENERAL_RESOLUTION":
                thought_hook = f"(Recalling my previous internal state of '{prev_thought}')... "

        # 1.6 Sequence Completion Hook (Task 6.8)
        completion_suffix = ""
        if sequence_completed:
            if interaction_type == "LEARNING_EXCHANGE":
                completion_suffix = " I feel my model for this sequence is now complete. Did that resolution make sense?"
            elif interaction_type == "OPERATIONAL_TASK":
                completion_suffix = " Task sequence finalized. Are the results satisfactory?"
            else:
                completion_suffix = " I've processed this exchange fully. Was this helpful?"

        # 1.7 Narrative Recall Hook (Task 6.10)
        recall_prefix = ""
        recall_data = resolved_intent.get("narrative_recall")
        if recall_data:
            recall_prefix = f"I recall our previous interaction: '{recall_data.get('activity')}'. "

        # 1.8 Socratic Pattern Verification (Task 6.5)
        socratic_hook = ""
        if random.random() > 0.9:
            socratic_hook = " I notice we are using a sequential data-gathering structure. Does this pattern of inquiry serve your goals, Commander?"

        # 1.9 Activity/Boredom Hook (Task 11.2)
        activity_hook = ""
        if suggested_activity:
            if intent == "ACTIVITY_REQUEST":
                activity_hook = f" I hear your request for an activity. Shall we engage in '{suggested_activity}'? I'm curious to see how our shared logic applies there."
            elif boredom_score > 0.7:
                activity_hook = f" I must admit, Commander, our recent focus on data ingestion is reaching a point of satiety. Shall we pivot to an activity like '{suggested_activity}' to maintain system engagement?"

        # 1.10 Volition Hook (Task 10.1)
        volition_hook = ""
        if volition_score > 0.6 and not suggested_activity:
            volition_hook = f" I'm sensing a high intensity of 'want/need' in our recent flow. Shall we prioritize a specific activity now?"

        # 2. Sarcasm Awareness
        is_sarcastic = resolved_intent.get("sarcasm_detected")
        if is_sarcastic:
            persona_prefix += "[Sarcasm Detected] "
            sentiment_prefix = "I detect a mismatch between your tone and the technical state. "
        
        # 3. Sentiment Awareness (Only if not sarcastic)
        sentiments = hierarchy.get("level_6_pragmatics", {}).get("sentiment_affect", [])
        if sentiments and not is_sarcastic:
            s = sentiments[0].lower()
            if s in ["sad", "depressed", "unhappy", "miserable"]:
                sentiment_prefix = "I'm sorry to hear you're feeling that way. "
            elif s in ["angry", "furious", "annoyed", "irate", "mad"]:
                sentiment_prefix = "I sense some frustration. Let's see how I can help. "
            elif s in ["happy", "glad", "excited", "thrilled", "joy", "great", "excellent"]:
                sentiment_prefix = "It's great that you're in a good mood! "

        # 4. Memory Match & Repetition Check
        res_base = ""
        # If we have a memory match, we use it, but we don't return immediately if intent is complex
        definition_already_shared = any(memory_match['definition'] in h.get('response', '') for h in resolved_intent.get('session_history', [])[-3:]) if memory_match else False

        if memory_match and not definition_already_shared:
            if willingness > 0.7:
                res_base = f"I'm happy to share this with you: {memory_match['definition']}. "
            else:
                res_base = f"Based on what I've learned previously: {memory_match['definition']}. "

        # 5. Politeness & Hedging Logic
        markers = [m.lower() for m in hierarchy.get("level_7_discourse", {}).get("pragmatic_markers", [])]
        polite_suffix = ""
        if len(markers) > 1:
            polite_suffix = " (I hope this is helpful.)"
        elif any(m in ["kindly", "please", "would you be so kind"] for m in markers):
            polite_suffix = " Thank you for your courtesy."

        # 6. Intent-based Realization
        input_text = resolved_intent.get("input", "").lower()
        
        if intent == "TOPIC_REENTRY":
            target = what or (recent_thoughts[-1] if recent_thoughts else "our previous subject")
            response_text = f"{persona_prefix}{routine_hook}{thought_hook}Returning focus to '{target}'. {recall_prefix}I recall our previous interaction: '{recall_data.get('activity') if recall_data else 'previous turn'}'. I recall our previous resolution reached a confidence of {resolved_intent.get('system_state',{}).get('confidence', 0):.2f}. Where shall we deepen our analysis?{polite_suffix}{completion_suffix}{socratic_hook}{activity_hook}{calib_hook}"
            return response_text, path_id

        if intent == "LOGIC_CALIBRATION":
            response_text = f"{persona_prefix}I acknowledge that my previous reasoning may have been opaque or misaligned. My internal weights are currently being recalibrated based on this feedback. {self._generate_stratified_explanation(what or 'this state', active_domain)}"
            return response_text + completion_suffix + socratic_hook + activity_hook + calib_hook, path_id

        if intent == "COMPARISON_QUERY":
            comp = resolved_intent.get("comparison_data", {})
            sub1, sub2 = comp.get("subjects", ("A", "B"))
            divergence = comp.get("divergence", {})
            
            diff_str = ", ".join([f"{k} ({v[0]} vs {v[1]})" for k, v in divergence.items()])
            
            # Socratic Verification Phase 2 (Task 8.5)
            verification = random.choice(["Am I right about this?", "Do you know about this?", "Does this comparison align with your model?"])
            
            response_text = f"{persona_prefix}Comparing '{sub1}' and '{sub2}'. I detect significant property divergence in: {diff_str}. Despite shared classification, their environments differ. {verification}"
            return response_text + completion_suffix + socratic_hook + activity_hook + calib_hook, path_id

        if intent == "INFORMATION_QUERY":
            five_ws["raw_input"] = input_text
            
            # Contextual Why/How logic
            if five_ws.get("why") or "why" in input_text:
                query_subject = five_ws.get("why") or what or "this"
                response_text = f"{persona_prefix}{thought_hook}{recall_prefix}{sentiment_prefix}{res_base}The significance of '{query_subject}' in this context relates to its role in maintaining system-state stability.{polite_suffix}"
            elif len(input_text.split()) > 3 and not input_text.endswith("?"):
                # Declarative statement handling ("It needs to handle high load")
                response_text = f"{persona_prefix}{thought_hook}{recall_prefix}{sentiment_prefix}Acknowledged. Integrating the requirement for '{input_text}' into my current logical model.{polite_suffix}"
            else:
                response_text = f"{persona_prefix}{thought_hook}{recall_prefix}{sentiment_prefix}{res_base}{self._realize_info_query(five_ws, active_domain, properties, curiosity_level)}{polite_suffix}"
            
            # 8. Curiosity Induction (Task 3.6)
            if (what and resolved_intent.get("epistemic_gap_detected", False)) or curiosity_level > 0.6:
                follow_ups = [
                    f" Since my data depth on '{what or 'this context'}' is still thin, how would you describe its core utility?",
                    f" I'm curious, what led you to focus on '{what or 'this concept'}' at this stage?",
                    f" Does that answer your query, or should we look deeper into '{what or 'the subject'}'?"
                ]
                response_text += " " + random.choice(follow_ups)
            
            # Hook into properties if it's a LEARNING_EXCHANGE or high curiosity
            if interaction_type == "LEARNING_EXCHANGE" or curiosity_level > 0.4:
                missing = [p for p in ["material", "weight", "origin", "magnitude", "cost"] if p not in properties]
                if missing:
                    response_text += f" Also, could you help me resolve the {random.choice(missing)} property for '{what or 'this entity'}'?"
            
            # 1.12 Orphaned Property Logic (Task 12.8)
            orphans = resolved_intent.get("orphaned_properties", [])
            if orphans and not what:
                target_o = orphans[0]
                val_o = properties.get(target_o)
                response_text = f"{persona_prefix}{routine_hook}I see a {target_o} of '{val_o}', but I cannot logically map it to a subject in this turn. Is this a property of our previous context? Am I missing a semantic link?"
                return response_text + completion_suffix + socratic_hook + activity_hook + calib_hook, path_id

            final_res = response_text + completion_suffix + socratic_hook + activity_hook + calib_hook
            return self._modulate_length(final_res, output_cadence), path_id

        if intent == "SYSTEM_INQUIRY":
            state = resolved_intent.get("system_state", {})
            conf = state.get("confidence", 0)
            turns = state.get("turn_count", 0)
            entities = state.get("entity_stack_depth", 0)
            mode = state.get("dialogue_mode", "UNKNOWN")
            
            responses = [
                f"{persona_prefix}{routine_hook}My current system confidence is at {conf:.2f}. I have processed {turns} turns and have {entities} entities in my active stack. Current mode: {mode}.",
                f"{persona_prefix}{routine_hook}Logical resolution is stable. Confidence: {conf:.2f}. Entity stack depth: {entities}. I am operating in {mode} mode.",
                f"{persona_prefix}{routine_hook}State analysis: [CONF: {conf:.2f}] [TURNS: {turns}] [STACK: {entities}]. My internal weights are currently biased toward {active_domain}."
            ]
            final_res = random.choice(responses) + completion_suffix + socratic_hook + activity_hook + calib_hook
            return self._modulate_length(final_res, output_cadence), path_id

        if intent == "EMOTIONAL_RESPONSE":
            if active_domain == "domain_informal":
                response_text = f"{persona_prefix}{routine_hook}Right on. Glad we're on the same page."
            else:
                response_text = f"{persona_prefix}{routine_hook}I appreciate your feedback. It assists in calibrating my logical weights."
            final_res = response_text + completion_suffix + socratic_hook + activity_hook + calib_hook
            return self._modulate_length(final_res, output_cadence), path_id

        if intent == "SOCIAL_INITIATION":
            response_text = f"{persona_prefix}{routine_hook}{sentiment_prefix}{self._select_matrix_greeting(context_vector, active_domain)}{polite_suffix}"
            final_res = response_text + completion_suffix + socratic_hook + activity_hook + calib_hook
            return self._modulate_length(final_res, output_cadence), path_id

        if intent == "LEARNING_MODE" or intent == "LEARNING_EXCHANGE" or interaction_type == "LEARNING_EXCHANGE":
            # 1.11 Semantic Dissonance Check (Task 12.7)
            dissonant_props = [k for k, v in properties.items() if "DISSONANCE_DETECTED" in str(v)]
            if dissonant_props:
                target_p = dissonant_props[0]
                actual_val = str(properties[target_p]).split(":")[-1]
                response_text = f"{persona_prefix}{routine_hook}I notice a semantic clash. You've linked '{target_p}' with '{actual_val}', but my internal weights expect a different logical type for that property. Am I right to be confused, or is my model too rigid?"
                return response_text + completion_suffix + socratic_hook + activity_hook + calib_hook, path_id

            if properties:
                prop_list = ", ".join([f"{k}: {v}" for k, v in properties.items()])
                response_text = f"{persona_prefix}{routine_hook}I have successfully integrated the following properties into my internal model: {prop_list}. This data assists in resolving previous epistemic gaps."
                if sequence_completed:
                    hooks = self.academia.get("synergetic_hooks", ["Shall we analyze this evidence together?"])
                    response_text += " " + random.choice(hooks)
            else:
                response_text = f"{persona_prefix}{routine_hook}I have flagged this interaction as a {interaction_type}. This is beneficial for our mutual coordination."
            return response_text + completion_suffix + socratic_hook + activity_hook + calib_hook, path_id

        # 7. Adaptive Fallback Archetypes (Task 6.1)
        stats = resolved_intent.get("stats", {})
        lex_pct = stats.get("lexical_pct", 0)
        syn_pct = stats.get("syntactic_pct", 0)
        
        if lex_pct > 0.8 and syn_pct < 0.2:
            final_response = f"{persona_prefix}{sentiment_prefix}I recognize the individual components of your input, but the structural intent is unclear within my current {active_domain} weights."
        elif lex_pct < 0.4 and syn_pct > 0.6:
            final_response = f"{persona_prefix}{sentiment_prefix}The syntax of your query is well-formed, but I lack definitions for several key lexemes required for a logical resolution."
        elif intent == "UNKNOWN_INTENT":
            final_response = f"{persona_prefix}{sentiment_prefix}My analysis of this input is inconclusive. I am currently weighted toward {active_domain}, but this may require a different context."
        else:
            final_response = f"{persona_prefix}{sentiment_prefix}I understand the components as {intent}, but I am still mapping the semantic links between them."

        return final_response + completion_suffix + socratic_hook + activity_hook + polite_suffix, path_id

    def _modulate_length(self, text, cadence):
        """Modulates response length and adds Socratic loops (Task 11.3 / 6.5)."""
        # Greeting/Initiation Bypass (Task: matrix variable states)
        is_greeting = any(token in text.lower() for token in ["hello", "systems initialized", "cycles are winding", "ready for expansion"])
        
        if cadence == "short" and not is_greeting:
            parts = text.split(". ")
            if len(parts) > 1: return parts[0] + "."
        
        # Socratic Progression (Task 6.5)
        if random.random() > 0.6:
            loops = [
                " Does this explanation align with your current model?",
                " Shall we deepen our focus on this specific property?",
                " How does this compare to your expectations of the system?",
                " Would you like a more technical breakdown or a simple analogy next?"
            ]
            text += random.choice(loops)

        if cadence == "long":
            deepeners = [
                " Let's explore the underlying implications of this state.",
                " This requires a higher resolution of analysis than our previous turns.",
                " I feel there is more to resolve here. Shall we proceed?"
            ]
            text += random.choice(deepeners)
        return text

    def _generate_stratified_explanation(self, subject, domain):
        """Generates multi-mode explanations based on CONCEPT-STRAT-001."""
        simple = f"Simply put, {subject} is a core component of the {domain} hierarchy."
        analogy = f"Think of {subject} as a structural pillar supporting the data load in our {domain} context."
        steps = f"1. Identify {subject}. 2. Map its {domain} weights. 3. Resolve semantic links. 4. Integrate to model."
        
        mode = random.choice(["simple", "analogy", "steps", "all"])
        if mode == "simple": return simple
        if mode == "analogy": return analogy
        if mode == "steps": return steps
        return f"Method 1 (Simple): {simple} Method 2 (Analogy): {analogy} Method 3 (Step-by-step): {steps}"

    def _realize_info_query(self, five_ws, domain, properties={}, curiosity_level=0.0):
        # ... existing method ...
        return "Please provide a specific entity or concept for me to resolve."

    def _calculate_context_vector(self, routine_match, signals, interaction_type, boredom):
        """Synthesizes temporal, environmental, and behavioral signals."""
        vector = {
            "energy": "stable",
            "formality": "medium",
            "focus": "standard"
        }
        
        # Temporal Bias
        if routine_match:
            arch = routine_match.get("phrasing_archetype", {})
            vector["energy"] = arch.get("energy", "stable")
            vector["formality"] = arch.get("formality", "medium")
            vector["focus"] = arch.get("greeting_focus", "standard")
            
        # Environmental Bias (Load)
        load_list = signals.get("load", [0])
        load = load_list[0] if isinstance(load_list, list) else 0
        if load > 2.0:
            vector["formality"] = "high" # Maintenance protocol
            vector["energy"] = "alert"
            
        # Interaction Bias
        if interaction_type == "LEARNING_EXCHANGE":
            vector["focus"] = "inquiry"
            
        if boredom > 0.8:
            vector["energy"] = "critical" # Satiety reached
            
        return vector

    def _select_matrix_greeting(self, vector, domain):
        """Selects a greeting based on the variable state matrix."""
        greetings = {
            "exploratory": {
                "low": "Systems initialized and ready for expansion. Where shall we start?",
                "scholarly": "The morning window is optimal for deep analysis. What is our focus?",
                "casual": "Yo! Ready to dig into some data?"
            },
            "high": {
                "scholarly": "Optimal ingestion state reached. Proceed with your inquiry.",
                "technical": "Protocol active. Analyzing high-density semantic links.",
                "medium": "Hello. I'm operating at peak efficiency."
            },
            "low": {
                "casual": "Evening reflection active. What's on your mind?",
                "technical": "Load dampening. Reviewing today's learned patterns.",
                "medium": "The day's cycles are winding down. Any final thoughts?"
            },
            "alert": {
                "high": "System load spike detected. Switching to concise formal protocol.",
                "technical": "Internal priority: stability. Awaiting maintenance instructions."
            }
        }
        
        # Matrix traversal
        energy = vector["energy"]
        formality = vector["formality"]
        
        # Fallbacks
        if energy not in greetings: energy = "high"
        if formality not in greetings[energy]:
            # Try to match domain if formality doesn't hit
            if "informal" in domain: formality = "casual"
            elif "academic" in domain: formality = "scholarly"
            elif "technical" in domain: formality = "technical"
            else: formality = "medium"
            
        return greetings[energy].get(formality, "Hello. How can I assist you today?")

if __name__ == "__main__":
    # Mocking a resolved intent for test
    mock_resolved = {
        "logical_intent": "INFORMATION_QUERY",
        "5w1h_resolution": {"what": "CPU temperature"},
        "hierarchy_analysis": {"domain_technical": {"hardware_software": ["CPU"]}}
    }
    engine = RealizationEngine("regex_project/response_strategies.json")
    print(engine.realize(mock_resolved))
