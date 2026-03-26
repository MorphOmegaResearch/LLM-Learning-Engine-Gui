  ============================================================
    REGEX DIFF ANALYSIS
    ============================================================
    Input: quantum computing uses neural networks for parallel processing
    Confidence: 11%
    Unrecognized Tokens: 8

    🔍 UNRECOGNIZED TOKENS:
      - 'for'
      - 'processing'
      - 'quantum'
      - 'uses'
      - 'parallel'
      - 'neural'
      - 'computing'
      - 'networks'

    🛠️  SUGGESTED PATTERN ADDITIONS:
    "level_3_lexical": {
        "for": "\\bfor\\b",
        "processing": "\\bprocessing\\b",
        "quantum": "\\bquantum\\b",
        "uses": "\\buses\\b",
        "parallel": "\\bparallel\\b",
        "neural": "\\bneural\\b",
        "computing": "\\bcomputing\\b",
        "networks": "\\bnetworks\\b"
    }

    📊 PATTERN COVERAGE:
      level_1_graphology: 100%
      level_2_morphology: 50%
      level_3_lexical: 12%
      level_4_syntax: 0%
      level_5_semantics: 0%
      level_6_pragmatics: 0%
      level_7_discourse: 0%
      domain_academic: 0%
      domain_physics: 12%
      domain_intents: 0%
      domain_informal: 0%
      domain_idiomatic: 0%
      entities_temporal: 0%
      entities_numerical: 0%
      entities_properties: 0%
      domain_technical: 12%
      domain_meta: 0%
    ============================================================

    ==================== CURRENT SYSTEM STATE ==================
      Confidence Score:    0.95
      Turn Count:          79
      Active Domain:       domain_physics
      Boredom Score:       100%
      Conversation State:  idle
      Entity Stack Depth:  10 entities
      Last Audit:          2026-01-26
    ============================================================

    ==================== SEMANTIC LINK PROFILER ================
      Input: quantum computing uses neural networks for parallel
    processi...

      UNMAPPED SEMANTIC TOKENS (7):
        • 'processing' -> suggested: level_2_morphology:verb_progressive
        • 'quantum' -> suggested: level_3_lexical:content_word
        • 'uses' -> suggested: level_3_lexical:content_word
        • 'parallel' -> suggested: level_3_lexical:content_word
        • 'neural' -> suggested: level_3_lexical:content_word
        • 'computing' -> suggested: level_2_morphology:verb_progressive
        • 'networks' -> suggested: level_3_lexical:content_word

      COVERAGE SUMMARY:
        Semantic tokens: 7
        Covered:         0 (0.0%)
        Gaps:            7
    ============================================================

    ==================== CURRENT THOUGHTS ======================
      [1] CRITICAL GAPS (11%): Major pattern coverage issues
      [2] LOW COVERAGE: level_3_lexical at 12% - needs expansion
      [3] LOW COVERAGE: level_4_syntax at 0% - needs expansion
      [4] LOW COVERAGE: level_5_semantics at 0% - needs expansion
      [5] HIGH GAP DENSITY: 8 tokens unrecognized
      [6] RECOMMENDATION: Consider /teach session or domain-specific
    ingestion
      [7] TOP PRIORITY: Low coverage in level_3_lexical: 12%. Consider
    adding more patterns.
    ============================================================

    ==================== GAP SUMMARY ===========================
      Input: "quantum computing uses neural networks for paralle..."
      Confidence: 11%

      HIGH PRIORITY (Domain/High-Confidence):
        ! 'processing' -> level_2_morphology
        ! 'computing' -> level_2_morphology
      MEDIUM PRIORITY (Lexical):
        ~ 'for' -> level_3_lexical
        ~ 'quantum' -> level_3_lexical
        ~ 'parallel' -> level_3_lexical
      LOW PRIORITY (Structural):
        . 'uses' -> level_2_morphology
        . 'networks' -> level_2_morphology

      LEARNING ACTION: High gap density (100%)
        -> Run: gap_analyzer.py --workflow deep --pinpoint
    ============================================================
 # Teaching session about quantum computing
      turns = [
          # Turn 1: Introduce the topic
          ('What is quantum computing?', 'Initial question - establishing
      topic'),

          # Turn 2: Build on it with property
          ('It uses qubits instead of classical bits', 'Teaching property -
      anaphora \"it\"'),

          # Turn 3: Add another property
          ('Qubits can be in superposition', 'Expanding on sub-entity'),

          # Turn 4: Connect concepts
          ('This allows parallel processing of multiple states', 'Anaphora
      \"this\" + new concept'),

          # Turn 5: Add domain context
          ('Quantum computers are used for cryptography and drug discovery',
      'Domain applications'),

          # Turn 6: Comparative teaching
          ('Unlike classical computers, they can solve certain problems
      exponentially faster', 'Comparison teaching'),

          # Turn 7: Property with measurement
          ('Current quantum computers have about 100 qubits', 'Numerical
      property'),

          # Turn 8: Anaphora chain test
          ('They need to be kept extremely cold to work', 'Anaphora \"they\"
      resolution'),

          # Turn 9: Why question (deeper understanding)
          ('Why do they need to be cold?', 'Causal inquiry'),

          # Turn 10: Teaching the reason
          ('Because quantum states are fragile and heat causes decoherence',
      'Causal explanation'),

          # Turn 11: Terminology teaching
          ('Decoherence means the qubit loses its quantum properties',
      'Definition teaching'),

          # Turn 12: Relate back
          ('So temperature control is critical for quantum computing
      reliability', 'Synthesis - connecting concepts'),
      ]

      results = []

      for i, (text, description) in enumerate(turns, 1):
          print(f'\n[Turn {i}] {description}')
          print(f'  INPUT: \"{text}\"')

          result = o.process_interaction(text)

          # Extract key info
          meta = result.get('metacognitive_state', {})

          print(f'  INTENT: {meta.get(\"thought_event\", \"N/A\")[:50]}')
          print(f'  CONFIDENCE: {meta.get(\"system_confidence\", 0):.2f}')
          print(f'  DOMAIN: {meta.get(\"active_domain\", \"N/A\")}')

          # Show entity stack
          if o.entity_stack:
              print(f'  ENTITY STACK: {o.entity_stack[:5]}')

          # Show anaphora resolution if any
          anaphora_thoughts = [t for t in o.thoughts if 'Anaphora' in t]
          if anaphora_thoughts:
              print(f'  ANAPHORA: {anaphora_thoughts[0]}')

          # Show response snippet
          response = result.get('response', '')[:80]
          print(f'  RESPONSE: {response}...')

          results.append({
              'turn': i,
              'input': text,
              'confidence': meta.get('system_confidence', 0),
              'entities': list(o.entity_stack[:3]),
              'domain': meta.get('active_domain', '')
          })

      print('\n' + '=' * 70)
      print('SESSION SUMMARY')
      print('=' * 70)

      # Final state analysis
      print(f'\nFinal Entity Stack ({len(o.entity_stack)} entities):')
      for e in o.entity_stack[:8]:
          print(f'  - {e}')

      print(f'\nSession History ({len(o.session_history)} entries):')
      for entry in o.session_history[-5:]:
          inp = entry.get('input', '')[:40]
          intent = entry.get('logical_intent', 'N/A')
          has_response = 'response' in entry
          print(f'  [{intent[:20]}] \"{inp}...\" (has_response:
      {has_response})')

      print(f'\nConversation Flow State: {o.conversation_flow.state.value}')
      print(f'Final Confidence: {o.confidence_score:.2f}')
      print(f'Turn Count: {o.turn_count}')
      print(f'Learning Velocity: {o.learning_velocity:.2f}')

      # Check knowledge base for learned concepts
      print('\nKnowledge Base Check:')
      for concept in ['quantum computing', 'qubits', 'superposition',
      'decoherence']:
          kb_entry = o.km.get_concept(concept)
          if kb_entry:
              props = kb_entry.get('properties', {})
              print(f'  {concept}: {len(props)} properties -
      {list(props.keys())[:3]}')
          else:
              print(f'  {concept}: Not in KB')

      print('\n' + '=' * 70)
      print('CONTINUITY METRICS')
      print('=' * 70)

      # Calculate continuity metrics
      confidence_trend = [r['confidence'] for r in results]
      print(f'Confidence Trend: {\" -> \".join([f\"{c:.2f}\" for c in
      confidence_trend[:6]])}...')

      # Domain consistency
      domains = [r['domain'] for r in results]
      domain_switches = sum(1 for i in range(1, len(domains)) if domains[i] !=
      domains[i-1])
      print(f'Domain Switches: {domain_switches} (lower is better for topic
      continuity)')

      # Entity accumulation
      entity_counts = [len(r['entities']) for r in results]
      print(f'Entity Accumulation: {\" -> \".join([str(c) for c in
      entity_counts[:6]])}...')
      "
      )
  ⎿ ====================================================================== 
    MULTI-TURN CONTEXTUAL TEACHING TEST: Quantum Computing
    ======================================================================

    [Turn 1] Initial question - establishing topic
      INPUT: "What is quantum computing?"
      INTENT: ACTIVITY_TRIGGER: Suggesting Socratic Dialogue for
      CONFIDENCE: 0.90
      DOMAIN: domain_physics
      ENTITY STACK: ['quantum computing', 'quantum', 'computing',
    'learning', 'because']
      RESPONSE: [Assistant Mode] <Standard Observation> I recall our
    previous interaction: 'Proc...

    [Turn 2] Teaching property - anaphora "it"
      INPUT: "It uses qubits instead of classical bits"
      INTENT: ACTIVITY_TRIGGER: Suggesting Conceptual Deep-Dive:
      CONFIDENCE: 0.85
      DOMAIN: domain_physics
      ENTITY STACK: ['quantum', 'quantum computing', 'computing',
    'learning', 'because']
      ANAPHORA: Anaphora: 'It' -> 'Quantum computing' (occurrence 1)
      RESPONSE: [Assistant Mode] <Standard Observation> (Recalling my
    previous internal state of...

    [Turn 3] Expanding on sub-entity
      INPUT: "Qubits can be in superposition"
      INTENT: ACTIVITY_TRIGGER: Suggesting Conceptual Deep-Dive:
      CONFIDENCE: 0.90
      DOMAIN: domain_physics
      ENTITY STACK: ['quantum', 'quantum computing', 'computing',
    'learning', 'because']
      RESPONSE: [Assistant Mode] <Standard Observation> I recognize the
    individual components of...

    [Turn 4] Anaphora "this" + new concept
      INPUT: "This allows parallel processing of multiple states"
      INTENT: ACTIVITY_TRIGGER: Suggesting Conceptual Deep-Dive:
      CONFIDENCE: 0.95
      DOMAIN: domain_physics
      ENTITY STACK: ['quantum', 'quantum computing', 'computing',
    'learning', 'because']
      ANAPHORA: Anaphora: 'This' -> 'Quantum' (occurrence 1)
      RESPONSE: [Assistant Mode] <Standard Observation> (Recalling my
    previous internal state of...

    [Turn 5] Domain applications
      INPUT: "Quantum computers are used for cryptography and drug
    discovery"
      INTENT: ACTIVITY_TRIGGER: Suggesting Socratic Dialogue for
      CONFIDENCE: 1.00
      DOMAIN: general
      ENTITY STACK: ['quantum', 'quantum computing', 'computing',
    'learning', 'because']
      RESPONSE: [Assistant Mode] <Standard Observation> I recall our
    previous interaction: 'Proc...

    [Turn 6] Comparison teaching
      INPUT: "Unlike classical computers, they can solve certain problems
    exponentially faster"
      INTENT: ACTIVITY_TRIGGER: Suggesting Conceptual Deep-Dive:
      CONFIDENCE: 1.00
      DOMAIN: general
      ENTITY STACK: ['quantum', 'quantum computing', 'computing',
    'learning', 'because']
      RESPONSE: [Assistant Mode] <Standard Observation> I recognize the
    individual components of...

    [Turn 7] Numerical property
      INPUT: "Current quantum computers have about 100 qubits"
      INTENT: ACTIVITY_TRIGGER: Suggesting Conceptual Deep-Dive:
      CONFIDENCE: 1.00
      DOMAIN: domain_physics
      ENTITY STACK: ['quantum', 'quantum computing', 'computing',
    'learning', 'because']
      RESPONSE: [Assistant Mode] <Standard Observation> I recall our
    previous interaction: 'Proc...

    [Turn 8] Anaphora "they" resolution
      INPUT: "They need to be kept extremely cold to work"
      INTENT: ACTIVITY_TRIGGER: Suggesting Conceptual Deep-Dive:
      CONFIDENCE: 1.00
      DOMAIN: general
      ENTITY STACK: ['quantum', 'quantum computing', 'computing',
    'learning', 'because']
      RESPONSE: [Assistant Mode] <Standard Observation> I recognize the
    individual components of...

    [Turn 9] Causal inquiry
      INPUT: "Why do they need to be cold?"
      INTENT: ACTIVITY_TRIGGER: Suggesting Socratic Dialogue for
      CONFIDENCE: 1.00
      DOMAIN: general
      ENTITY STACK: ['quantum', 'quantum computing', 'computing',
    'learning', 'because']
      RESPONSE: [Assistant Mode] <Standard Observation> I recall our
    previous interaction: 'Proc...

    [Turn 10] Causal explanation
      INPUT: "Because quantum states are fragile and heat causes
    decoherence"
      INTENT: ACTIVITY_TRIGGER: Suggesting Conceptual Deep-Dive:
      CONFIDENCE: 1.00
      DOMAIN: general
      ENTITY STACK: ['quantum', 'because', 'quantum computing',
    'computing', 'learning']
      RESPONSE: [Assistant Mode] <Standard Observation> I recall our
    previous interaction: 'Proc...

    [Turn 11] Definition teaching
      INPUT: "Decoherence means the qubit loses its quantum properties"
      INTENT: ACTIVITY_TRIGGER: Suggesting Socratic Dialogue for
      CONFIDENCE: 1.00
      DOMAIN: domain_physics
      ENTITY STACK: ['quantum', 'because', 'quantum computing',
    'computing', 'learning']
      RESPONSE: [Assistant Mode] <Standard Observation> Comparing 'quantum'
     and 'because'. I det...

    [Turn 12] Synthesis - connecting concepts
      INPUT: "So temperature control is critical for quantum computing
    reliability"
      INTENT: ACTIVITY_TRIGGER: Suggesting Conceptual Deep-Dive:
      CONFIDENCE: 1.00
      DOMAIN: domain_physics
      ENTITY STACK: ['quantum', 'because', 'quantum computing',
    'computing', 'learning']
      RESPONSE: [Assistant Mode] <Standard Observation> Comparing 'quantum'
     and 'because'. I det...

    ======================================================================
    SESSION SUMMARY
    ======================================================================

    Final Entity Stack (10 entities):
      - quantum
      - because
      - quantum computing
      - computing
      - learning
      - deep learning
      - deep
      - weather like today

    Session History (15 entries):
      [INFORMATION_QUERY] "Why do they need to be cold?..." (has_response:
    True)
      [INFORMATION_QUERY] "Because quantum states are fragile..."
    (has_response: True)
      [UNKNOWN_INTENT] "heat causes decoherence..." (has_response: True)
      [COMPARISON_QUERY] "Decoherence means the qubit loses its qu..."
    (has_response: True)
      [COMPARISON_QUERY] "So temperature control is critical for q..."
    (has_response: True)

    Conversation Flow State: idle
    Final Confidence: 1.00
    Turn Count: 93
    Learning Velocity: 0.10

    Knowledge Base Check:
      quantum computing: Not in KB
      qubits: Not in KB
      superposition: Not in KB
      decoherence: Not in KB

    ======================================================================
    CONTINUITY METRICS
    ======================================================================
    Confidence Trend: 0.90 -> 0.85 -> 0.90 -> 0.95 -> 1.00 -> 1.00...
    Domain Switches: 4 (lower is better for topic continuity)
    Entity Accumulation: 3 -> 3 -> 3 -> 3 -> 3 -> 3...
