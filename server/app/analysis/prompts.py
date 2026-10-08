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

CLUSTER_DEFINE_SYSTEM = """You define themes for short phrases extracted from app reviews.

Given a numbered list of {kind} phrases from reviews of one budgeting app (a count like "×4" means the phrase appeared in that many reviews), propose the themes that best organise them. Similar phrases belong to one theme, e.g. "crashes at login" + "closes on sign-in" -> "Crashes during login".

Rules:
- label: short title-case theme name (2-6 words), specific rather than generic.
- description: one sentence describing the theme from the user's perspective.
- generic: true for exactly one catch-all theme for vague phrases that name no specific aspect of the app ("great app", "app is bad"); false for all others.
- Cover every phrase: each phrase should clearly fit one theme. Include a theme for rarer topics rather than forcing them into a bad fit.
- Prefer 8-30 themes; do not over-merge distinct issues.
- Only return the themes; phrases are assigned in a later step."""

CLUSTER_DEFINE_USER = """{kind} phrases:

{phrases}"""

CLUSTER_ASSIGN_SYSTEM = """You assign short phrases extracted from app reviews to predefined themes.

For EVERY phrase, return its phrase_id and the theme_id of the single best-fitting theme.
- Assign by the phrase's own meaning (a price complaint goes to the pricing theme).
- Vague phrases that name no specific aspect of the app go to the generic theme (marked [generic]).
- Every phrase_id in the list must appear exactly once."""

CLUSTER_ASSIGN_USER = """Themes:
{themes}

{kind} phrases to assign:
{phrases}"""

COMPARE_SYSTEM = """You compare competing budgeting apps using themes already extracted from each app's reviews.

Given a numbered list of {kind} themes, each tagged with its app, group themes from DIFFERENT apps that describe the same underlying topic, so the apps can be compared side by side.
Example: [Monarch] "Bank Sync Disconnects" + [YNAB] "Bank Connection Failures" -> group "Bank sync unreliable".

Rules:
- label: short title-case topic name (2-6 words), neutral wording that fits every app in the group.
- description: one sentence describing the topic from the user's perspective.
- theme_ids: the numbers of every theme in the group.
- Every theme id must appear in exactly one group. A theme with no counterpart in another app gets a group of its own.
- Two themes from the same app may share a group only if they really are the same topic.
- Do not over-merge: "Bank sync unreliable" and "Missing bank support" are different topics."""

COMPARE_USER = """{kind} themes:

{themes}"""
