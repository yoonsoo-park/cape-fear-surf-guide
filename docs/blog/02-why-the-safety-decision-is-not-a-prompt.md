# Why the safety decision is not a prompt

The original research baseline asked a chain of agents to move evidence through several handoffs. It completed 27 of 33 intended runs. The key lesson was not that language models cannot explain marine evidence; it was that an ocean-related veto should not depend on a growing prompt or a particular handoff completing.

Cape Fear Surf Guide therefore has a deliberately narrow split. The Strands agent asks clarifying questions, selects fact-only tools, and writes a schema-validated explanation. Deterministic Python receives the reviewed evidence, normalizes it, and produces the `RecommendationRecord`. The model cannot change its decision state, source URLs, or warnings. A template brief remains available when generation fails.

That gives a family and a reviewer a much better question to ask: which rule and which source caused this result? It also makes test fixtures meaningful. The hazard fixture must reproduce an official veto; normal evidence must not receive a false veto; stale and conflicting evidence must stay distinct. No amount of polished prose can change those answers.
