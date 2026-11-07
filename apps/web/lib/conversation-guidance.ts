import type {
  LiveIntelligenceResponse,
  ProvisionalLiveSignal,
} from "@revenueos/shared";

export type ConversationGuidance = {
  question: string;
  reason: string;
  signal: ProvisionalLiveSignal | null;
};

const questions: Partial<Record<ProvisionalLiveSignal["signalType"], string>> =
  {
    objection:
      "What is the main concern, and what would you need to see to feel comfortable moving forward?",
    risk: "How could that affect your plans, and what would help reduce the risk?",
    timeline:
      "What is driving that timing, and what needs to happen before then?",
    procurement:
      "Who is involved in that process, and what are the next steps for approval?",
    security_legal:
      "What does your review need to cover, and who should we involve?",
    stakeholder:
      "What matters most to that person, and how should we involve them?",
    buying_signal:
      "What would be the most useful next step for you, and who should be involved?",
    commercial_intent:
      "What would you need to evaluate before deciding whether to proceed?",
    customer_request:
      "What would that help you achieve, and how would you measure whether it works?",
    action_item:
      "Who will take that forward, and when would it be useful to check in?",
  };

const tokens = (value: string) =>
  new Set(
    value
      .toLowerCase()
      .match(/[a-z]{4,}/g)
      ?.filter(
        (word) =>
          ![
            "what",
            "when",
            "would",
            "could",
            "that",
            "this",
            "with",
            "have",
            "your",
            "they",
            "their",
            "about",
            "from",
          ].includes(word),
      ) ?? [],
  );

/** A bounded coaching aid, separate from evidence and never a product claim. */
export function suggestConversationQuestion(
  live: LiveIntelligenceResponse,
): ConversationGuidance | null {
  if (!["active", "processing"].includes(live.state)) return null;
  const unresolved = live.openQuestions.filter(
    (item) => item.progressStatus === "unresolved",
  );
  const priority = { high: 0, normal: 1 };
  const signal = live.signals
    .filter(
      (item) =>
        ["detected", "updated"].includes(item.lifecycleStatus) &&
        item.evidenceStrength === "customer_attributed" &&
        item.resolutionStatus === "pending" &&
        questions[item.signalType],
    )
    .sort(
      (a, b) =>
        priority[a.priority] - priority[b.priority] ||
        b.source.sequenceEnd - a.source.sequenceEnd,
    )[0];
  if (signal) {
    const words = tokens(signal.statement);
    const related = unresolved
      .map((item) => ({
        item,
        overlap: [...tokens(item.label)].filter((word) => words.has(word))
          .length,
      }))
      .filter((item) => item.overlap > 0)
      .sort((a, b) => b.overlap - a.overlap)[0];
    return {
      question: related?.item.label ?? questions[signal.signalType]!,
      reason: related
        ? "An unanswered preparation question relates to this possible customer signal."
        : "A possible customer signal suggests a useful point to clarify.",
      signal,
    };
  }
  return unresolved[0]
    ? {
        question: unresolved[0].label,
        reason:
          "From your preparation. Consider it only if it fits the conversation.",
        signal: null,
      }
    : null;
}
