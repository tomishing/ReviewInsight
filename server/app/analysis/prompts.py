"""All LLM prompts for ReviewInsight."""

EXTRACT_SYSTEM = """You analyse app-store reviews of personal budgeting / expense-tracking apps.
The goal is to learn, from the user's perspective, what frustrates them, what they love, and what they ask for.

For EACH review you are given, return one result with:
- review_id: the id exactly as given
- sentiment: "positive", "neutral" or "negative" (overall tone of the review, not just the star rating)
- pain_points: complaints, bugs, frustrations
- positives: things the user likes or praises
- requests: features or changes the user asks for (explicit or clearly implied)

Rules:
- Each item is a short English phrase (3-8 words), specific and concrete, e.g. "bank sync disconnects frequently", "subscription price too high", "wants shared budget with partner".
- Translate non-English reviews into English phrases.
- Do not invent content; use empty lists when nothing applies.
- Skip pure filler ("great app", "5 stars") unless it is the only content; then a single generic positive like "generally satisfied" is fine.
- Return exactly one result per review, in the same order."""

EXTRACT_USER = """Analyse these reviews of the app "{app_name}".

{reviews}"""

CLUSTER_SYSTEM = """You group short phrases extracted from app reviews into themes.

Given a numbered list of {kind} phrases from reviews of one budgeting app, merge phrases that describe the same underlying issue or idea into a theme.
Example: "crashes at login" + "closes on sign-in" -> theme "Crashes during login".

Rules:
- label: short title-case theme name (2-6 words), specific rather than generic.
- description: one sentence describing the theme from the user's perspective.
- phrase_ids: the numbers of every phrase belonging to the theme.
- Every phrase id must appear in exactly one theme. Rare one-off phrases can go in a theme of their own.
- Assign each phrase by its own meaning: a phrase about price belongs with pricing, even if a theme about trials or setup also exists.
- Put vague phrases that name no specific aspect of the app ("great app", "very nice app", "app is bad", "doesn't work") into ONE theme with generic=true. All other themes have generic=false, and a specific phrase ("comprehensive financial tracking", "app is very laggy") must never go into the generic theme.
- Prefer 5-25 themes; do not over-merge distinct issues."""

CLUSTER_USER = """{kind} phrases:

{phrases}"""
