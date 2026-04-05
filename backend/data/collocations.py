"""
English collocation data - loaded once at module level.

Two tables:
  VERB_OBJ_COLLOCATIONS  - noun → set of natural verbs that take it as object
  ADJ_NOUN_COLLOCATIONS  - noun → set of natural adjectives that modify it

Used by compute_collocation_signal() in backend/services/vocab.py to detect
non-native word combinations. If spaCy extracts a verb+object or adj+noun pair
and the verb/adj is NOT in the expected set for that noun, it is flagged as a
potential collocation error.

Coverage: ~300 high-frequency IELTS-relevant noun targets, focusing on
the verb-object and adjective-noun patterns that are most commonly confused
by non-native speakers.

Do NOT import this per-request - it is loaded once at module import time.
"""
from __future__ import annotations

# verb → object collocations
# Format: noun_lemma → frozenset of natural verb lemmas
# If a speaker uses a verb NOT in this set with this noun object, it is flagged.
VERB_OBJ_COLLOCATIONS: dict[str, frozenset[str]] = {
    # decisions and judgments
    "decision":    frozenset({"make", "take", "reach", "arrive", "come", "reverse", "reconsider"}),
    "choice":      frozenset({"make", "have", "face", "give"}),
    "judgment":    frozenset({"make", "pass", "form", "exercise"}),
    "conclusion":  frozenset({"reach", "draw", "come", "jump"}),
    "assumption":  frozenset({"make", "challenge", "question"}),
    # mistakes and problems
    "mistake":     frozenset({"make", "commit", "avoid", "correct", "repeat"}),
    "error":       frozenset({"make", "commit", "avoid", "correct", "spot"}),
    "blunder":     frozenset({"make", "commit"}),
    "problem":     frozenset({"cause", "create", "solve", "address", "tackle", "face", "pose", "raise", "encounter"}),
    "issue":       frozenset({"address", "tackle", "raise", "resolve", "face", "deal", "discuss"}),
    "challenge":   frozenset({"face", "meet", "overcome", "pose", "present", "tackle"}),
    "difficulty":  frozenset({"face", "overcome", "experience", "encounter", "cause"}),
    "damage":      frozenset({"cause", "do", "suffer", "repair", "assess", "prevent"}),
    "harm":        frozenset({"cause", "do", "prevent", "suffer", "avoid"}),
    # effort and achievement
    "effort":      frozenset({"make", "put", "require", "need"}),
    "attempt":     frozenset({"make"}),
    "progress":    frozenset({"make", "achieve"}),
    "improvement": frozenset({"make", "achieve", "see", "bring", "show"}),
    "difference":  frozenset({"make", "see", "notice"}),
    "impact":      frozenset({"have", "make", "feel", "create", "leave"}),
    "effect":      frozenset({"have", "produce", "achieve", "feel", "create"}),
    "influence":   frozenset({"have", "exert", "feel", "exercise"}),
    "change":      frozenset({"make", "bring", "cause", "create", "undergo", "see", "implement"}),
    "contribution": frozenset({"make"}),
    # roles and responsibilities
    "role":        frozenset({"play", "take", "assume", "have", "fulfill"}),
    "part":        frozenset({"play", "take"}),
    "responsibility": frozenset({"take", "have", "accept", "fulfill", "bear", "shoulder"}),
    "duty":        frozenset({"have", "fulfil", "carry", "perform"}),
    "advantage":   frozenset({"take", "have", "offer", "give", "gain"}),
    "opportunity": frozenset({"have", "take", "create", "miss", "give", "provide", "seize"}),
    "chance":      frozenset({"have", "give", "take", "miss", "get"}),
    # attention and thought
    "attention":   frozenset({"pay", "attract", "draw", "give", "receive", "devote"}),
    "care":        frozenset({"take", "provide"}),
    "thought":     frozenset({"give", "put", "devote", "spare"}),
    "consideration": frozenset({"give", "take", "show", "deserve"}),
    "interest":    frozenset({"have", "take", "show", "express", "develop", "spark"}),
    # experience and knowledge
    "experience":  frozenset({"have", "gain", "get", "acquire", "lack"}),
    "knowledge":   frozenset({"have", "gain", "acquire", "share", "lack", "apply", "transfer"}),
    "skill":       frozenset({"have", "develop", "learn", "acquire", "use", "apply", "improve", "build"}),
    "ability":     frozenset({"have", "develop", "lose", "demonstrate", "show"}),
    "education":   frozenset({"receive", "get", "have", "provide", "improve"}),
    # communication
    "speech":      frozenset({"give", "deliver", "make"}),
    "presentation": frozenset({"give", "deliver", "make", "prepare"}),
    "argument":    frozenset({"make", "present", "put", "support", "raise"}),
    "point":       frozenset({"make", "raise", "prove", "support"}),
    "suggestion":  frozenset({"make", "reject", "accept"}),
    "advice":      frozenset({"give", "take", "follow", "seek", "offer", "ask"}),
    "question":    frozenset({"ask", "raise", "answer", "address", "pose"}),
    # money and economy
    "money":       frozenset({"spend", "save", "earn", "make", "lose", "waste", "borrow", "lend", "invest"}),
    "profit":      frozenset({"make", "generate", "earn"}),
    "investment":  frozenset({"make", "attract", "require"}),
    "cost":        frozenset({"reduce", "cut", "increase", "raise", "cover"}),
    # time
    "time":        frozenset({"spend", "take", "waste", "save", "have", "use", "give", "need", "find"}),
    # relationships
    "relationship": frozenset({"have", "build", "develop", "maintain", "form", "strengthen", "damage", "end"}),
    "friendship":  frozenset({"have", "build", "form", "maintain", "develop", "value"}),
    "connection":  frozenset({"have", "make", "build", "form", "establish", "lose"}),
    # environment
    "environment": frozenset({"protect", "damage", "destroy", "preserve", "pollute", "affect"}),
    "pollution":   frozenset({"cause", "reduce", "fight", "prevent", "create", "tackle"}),
    "awareness":   frozenset({"raise", "increase", "have", "show", "create"}),
    # society / politics
    "law":         frozenset({"pass", "make", "break", "enforce", "change", "follow", "introduce"}),
    "rule":        frozenset({"follow", "break", "make", "enforce", "change", "introduce"}),
    "policy":      frozenset({"implement", "introduce", "adopt", "change", "follow", "develop"}),
    "solution":    frozenset({"find", "offer", "provide", "implement", "propose", "suggest"}),
    "measure":     frozenset({"take", "implement", "introduce"}),
    # health
    "risk":        frozenset({"take", "reduce", "minimize", "face", "pose", "present", "assess"}),
    "benefit":     frozenset({"have", "provide", "offer", "receive", "gain"}),
    "health":      frozenset({"improve", "maintain", "damage", "affect", "protect", "harm"}),
    # general
    "goal":        frozenset({"achieve", "set", "reach", "meet", "pursue", "have"}),
    "target":      frozenset({"achieve", "set", "reach", "meet", "miss"}),
    "plan":        frozenset({"make", "have", "develop", "implement", "change"}),
    "decision":    frozenset({"make", "take", "reach"}),
    "information": frozenset({"provide", "share", "gather", "collect", "give", "get", "have", "use"}),
    "support":     frozenset({"provide", "give", "receive", "get", "offer", "need", "show"}),
    "help":        frozenset({"provide", "give", "receive", "get", "offer", "need", "ask"}),
}

# adjective → noun collocations
# Format: noun_lemma → frozenset of natural adjective lemmas
ADJ_NOUN_COLLOCATIONS: dict[str, frozenset[str]] = {
    # weather
    "rain":        frozenset({"heavy", "light", "moderate", "torrential", "gentle"}),
    "wind":        frozenset({"strong", "gentle", "light", "powerful", "cold"}),
    "snow":        frozenset({"heavy", "light", "fresh", "deep"}),
    # physical quantities
    "majority":    frozenset({"vast", "large", "overwhelming", "slim", "small", "significant"}),
    "minority":    frozenset({"small", "large", "significant", "vocal"}),
    "number":      frozenset({"large", "small", "growing", "significant", "increasing", "great", "high"}),
    "amount":      frozenset({"large", "small", "significant", "considerable", "great", "huge", "vast"}),
    "range":       frozenset({"wide", "broad", "full", "narrow", "limited", "diverse"}),
    "variety":     frozenset({"wide", "broad", "great", "huge", "rich"}),
    # importance and value
    "role":        frozenset({"important", "key", "vital", "significant", "central", "critical", "major", "leading", "crucial"}),
    "impact":      frozenset({"significant", "major", "profound", "positive", "negative", "considerable", "great", "huge", "minimal"}),
    "effect":      frozenset({"positive", "negative", "significant", "profound", "adverse", "harmful", "beneficial", "lasting"}),
    "influence":   frozenset({"strong", "powerful", "significant", "great", "major", "positive", "negative"}),
    "importance":  frozenset({"great", "vital", "enormous", "paramount", "key"}),
    "benefit":     frozenset({"significant", "major", "potential", "clear", "obvious", "mutual"}),
    "advantage":   frozenset({"significant", "major", "clear", "obvious", "distinct", "competitive"}),
    "disadvantage": frozenset({"significant", "major", "clear", "obvious", "potential"}),
    # growth and change
    "increase":    frozenset({"significant", "dramatic", "sharp", "rapid", "steady", "gradual", "slight"}),
    "rise":        frozenset({"sharp", "dramatic", "rapid", "steady", "gradual", "significant"}),
    "growth":      frozenset({"rapid", "steady", "significant", "economic", "sustainable", "slow", "strong"}),
    "decline":     frozenset({"sharp", "dramatic", "significant", "rapid", "gradual", "steady", "slow"}),
    "improvement": frozenset({"significant", "major", "dramatic", "steady", "gradual", "considerable", "marked"}),
    # time
    "time":        frozenset({"long", "short", "free", "spare", "limited", "sufficient", "valuable", "leisure"}),
    "period":      frozenset({"long", "short", "extended", "brief", "significant"}),
    # problems and challenges
    "problem":     frozenset({"serious", "major", "significant", "growing", "common", "complex", "difficult", "real"}),
    "issue":       frozenset({"serious", "major", "significant", "complex", "controversial", "pressing", "key", "important"}),
    "challenge":   frozenset({"major", "significant", "great", "real", "key", "serious"}),
    "difficulty":  frozenset({"great", "serious", "main"}),
    "concern":     frozenset({"growing", "major", "serious", "real", "genuine", "common", "widespread"}),
    # society and people
    "society":     frozenset({"modern", "contemporary", "traditional", "western"}),
    "community":   frozenset({"local", "global", "wider", "international"}),
    "population":  frozenset({"growing", "ageing", "global", "entire", "local", "rural", "urban"}),
    "generation":  frozenset({"younger", "older", "current", "future", "next"}),
    # education
    "education":   frozenset({"good", "higher", "basic", "primary", "secondary", "quality", "formal"}),
    "skill":       frozenset({"important", "key", "essential", "valuable", "practical", "new", "social", "basic", "technical", "critical"}),
    "knowledge":   frozenset({"good", "basic", "extensive", "limited", "deep", "broad", "comprehensive", "practical"}),
    # environment
    "environment": frozenset({"natural", "built", "healthy", "clean", "safe", "local", "physical", "social"}),
    "pollution":   frozenset({"air", "water", "environmental", "industrial", "noise", "serious"}),
    # work and business
    "opportunity": frozenset({"good", "real", "great", "golden", "excellent", "valuable", "equal", "rare"}),
    "experience":  frozenset({"valuable", "good", "positive", "negative", "relevant", "practical", "rich", "real"}),
    "career":      frozenset({"successful", "long", "exciting", "rewarding", "promising", "professional"}),
    # development
    "development": frozenset({"economic", "sustainable", "social", "rapid", "recent", "future", "human", "significant"}),
    "technology":  frozenset({"modern", "new", "advanced", "digital", "information", "latest", "emerging"}),
    "progress":    frozenset({"significant", "rapid", "slow", "tremendous", "considerable", "real"}),
}
