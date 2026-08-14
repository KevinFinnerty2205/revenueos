# Debrief questioning strategy

The opening question is fixed and natural: “How did it go?”. Each subsequent turn
uses the strict `ai_debrief_question` schema: `status`, optional `question`, `reason`,
controlled `target` and controlled `priority`.

The application supplies a bounded context projection from the Interaction,
Opportunity, latest Pre-Interaction Brief, Revenue Brain latest state/longitudinal
insight, previous validated reported intelligence, answers and asked targets. Raw
transcripts and recordings are excluded.

Question policy prefers material unanswered changes: stakeholders/procurement,
budget, timeline, security/legal, objections/competitors, decisions, commitments,
implementation and next steps. Interaction-specific questions cover phone calls,
presentations, site visits, executive lunches, conferences and trade shows. It must
not repeat an answered target, run a checklist, infer that silence means no, invent a
fact, score/forecast, or propose an autonomous action.

The default maximum is six follow-up questions after the opener, configurable only
from one to ten. The user may finish after any answer. Explicit finish phrases,
sufficient evidence or the cap produce `status=complete`. Voice Journal uses the
separate extraction prompt and a two-question ceiling.

The deterministic mock implements the same contract and context rules. Automated
tests never call an external provider. Production evaluation should measure useful
question rate, duplicate/irrelevant question rate, early completion, correction and
unsupported-candidate rate without logging answer content.
