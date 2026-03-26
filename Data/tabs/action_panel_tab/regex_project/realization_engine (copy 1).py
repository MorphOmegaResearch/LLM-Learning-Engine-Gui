import json
import random

class RealizationEngine:
    """
    Translates Logical Intent and 5W1H into a natural language response.
    Uses Level-based constraints to ensure grammatical and contextual accuracy.
    """

    def __init__(self, strategies_path):
        with open(strategies_path, 'r') as f:
            self.strategies = json.load(f)

    def realize(self, resolved_intent, active_domain="general", active_persona="Assistant", memory_match=None, properties={}, willingness=0.5, mode="EXPLORATORY", interaction_type="GENERAL_EXCHANGE", curiosity_level=0.0, recent_thoughts=[], sequence_completed=False): #[Mark:REALIZE_CORE]
        """
        Synthesizes a response from the resolved interaction object.
        """
        signals = resolved_intent.get("system_signals", {})
        situation = resolved_intent.get("active_situation")
        intent = resolved_intent.get("logical_intent")
        five_ws = resolved_intent.get("5w1h_resolution")
        what = five_ws.get("what")
        hierarchy = resolved_intent.get("hierarchy_analysis", {})
        
        # 1. Persona and Situational Prefix
        persona_prefix = f"[{active_persona} Mode] "
        if situation:
            persona_prefix += f"<{situation}> "
        
        sentiment_prefix = ""

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
            return f"{persona_prefix}{thought_hook}Returning focus to '{target}'. {recall_prefix}I recall our previous resolution reached a confidence of {resolved_intent.get('system_state',{}).get('confidence', 0):.2f}. Where shall we deepen our analysis?{polite_suffix}{completion_suffix}"

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
            
            return response_text + completion_suffix

        if intent == "SYSTEM_INQUIRY":
            state = resolved_intent.get("system_state", {})
            conf = state.get("confidence", 0)
            turns = state.get("turn_count", 0)
            entities = state.get("entity_stack_depth", 0)
            mode = state.get("dialogue_mode", "UNKNOWN")
            
            responses = [
                f"{persona_prefix}My current system confidence is at {conf:.2f}. I have processed {turns} turns and have {entities} entities in my active stack. Current mode: {mode}.",
                f"{persona_prefix}Logical resolution is stable. Confidence: {conf:.2f}. Entity stack depth: {entities}. I am operating in {mode} mode.",
                f"{persona_prefix}State analysis: [CONF: {conf:.2f}] [TURNS: {turns}] [STACK: {entities}]. My internal weights are currently biased toward {active_domain}."
            ]
            return random.choice(responses) + completion_suffix

        if intent == "EMOTIONAL_RESPONSE":
            if active_domain == "domain_informal":
                response_text = f"{persona_prefix}Right on. Glad we're on the same page."
            else:
                response_text = f"{persona_prefix}I appreciate your feedback. It assists in calibrating my logical weights."
            return response_text + completion_suffix

        if intent == "SOCIAL_INITIATION":
            if active_domain == "domain_informal":
                response_text = f"{persona_prefix}{sentiment_prefix}Yo! What's up?{polite_suffix}"
            elif active_domain == "domain_academic":
                response_text = f"{persona_prefix}{sentiment_prefix}Salutations. How may I contribute to your research today?{polite_suffix}"
            else:
                response_text = f"{persona_prefix}{sentiment_prefix}Hello! How can I assist you today?{polite_suffix}"
            return response_text + completion_suffix

        if intent == "LEARNING_MODE" or intent == "LEARNING_EXCHANGE" or interaction_type == "LEARNING_EXCHANGE":
            if properties:
                prop_list = ", ".join([f"{k}: {v}" for k, v in properties.items()])
                response_text = f"{persona_prefix}I have successfully integrated the following properties into my internal model: {prop_list}. This data assists in resolving previous epistemic gaps."
            else:
                response_text = f"{persona_prefix}I have flagged this interaction as a LEARNING_EXCHANGE. This is beneficial for our mutual coordination. I am currently cross-mapping property context weights from my internal dream/story synthesis to resolve remaining epistemic gaps."
            return response_text + completion_suffix

        final_response = f"{persona_prefix}{sentiment_prefix}I understand the input as {intent} in the context of {active_domain}, but I am still refining my response logic.{polite_suffix}"
        
        # 1.8 Socratic Pattern Verification (Task 6.5)
        socratic_hook = ""
        if random.random() > 0.9:
            socratic_hook = " I notice we are using a sequential data-gathering structure. Does this pattern of inquiry serve your goals, Commander?"

        return final_response + completion_suffix + socratic_hook

    def _detect_domain(self, analysis):
        for level, cats in analysis.items():
            if level.startswith("domain_"):
                return level
        return "general"

    def _realize_info_query(self, five_ws, domain, properties={}, curiosity_level=0.0):
        what = five_ws.get("what")
        input_text = five_ws.get("raw_input", "").lower() # Needs raw input
        
        if what:
            # 1. Proactive Variable Inquiry (B.2)
            missing = []
            known_props = properties.keys()
            for p in ["material", "weight", "origin"]:
                if p not in known_props:
                    missing.append(p)
            
            # 2. General Temporal Fallback (Task 2.4)
            if not properties and len(what.split()) < 3 and "what" in input_text:
                return f"At this moment, my internal state is stable. We are focusing on {what}, though my data depth here is still foundational."

            # 3. Varied Fallbacks for unknown entities
            base_response = ""
            variations = [
                f"Analyzing '{what}' within the {domain} context... My current resolution is limited to conceptual definitions.",
                f"You are inquiring about '{what}'. In {domain} terms, this is a significant entity for our current analysis.",
                f"Regarding '{what}': The {domain} hierarchy suggests this is a key focus area.",
                f"I've indexed '{what}' as a high-priority concept in the {domain} domain, though I lack specific details.",
                f"The term '{what}' has been flagged for further study in the {domain} layer. Can you elaborate?"
            ]
            base_response = random.choice(variations)
            
            if missing and (random.random() > 0.3 or curiosity_level > 0.5):
                target_p = random.choice(missing)
                base_response += f" I notice I'm missing the {target_p} data for this entity. Could you provide that?"
            
            return base_response
        
        # 4. Fallback when 'what' is null but intent is QUERY
        return random.choice([
            "Could you please specify what information you are looking for?",
            "I'm ready to analyze, but I need a clearer subject.",
            "Please provide a specific entity or concept for me to resolve."
        ])

if __name__ == "__main__":
    # Mocking a resolved intent for test
    mock_resolved = {
        "logical_intent": "INFORMATION_QUERY",
        "5w1h_resolution": {"what": "CPU temperature"},
        "hierarchy_analysis": {"domain_technical": {"hardware_software": ["CPU"]}}
    }
    engine = RealizationEngine("regex_project/response_strategies.json")
    print(engine.realize(mock_resolved))
