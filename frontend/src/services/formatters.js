// Groups a TurnResponse.questions list (each with key/label/question/section) by section for
// a readable assistant message, mirroring the backend's existing section groupings.
export function groupedQuestionsBody(questions) {
  const sections = [];
  for (const q of questions) {
    let section = sections.find((s) => s.title === q.section);
    if (!section) {
      section = { title: q.section, items: [] };
      sections.push(section);
    }
    section.items.push(q);
  }
  let counter = 0;
  return sections
    .map((s) => `${s.title}:\n${s.items.map((q) => `${++counter}. ${q.question}`).join("\n")}`)
    .join("\n\n");
}

export function formatSubmission(submission) {
  return Object.entries(submission)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
}
