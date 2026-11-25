// The project's bug form, filled in from a problem report (the same fields the agent's
// report.py issue_url fills). GitHub has no way for a page to attach the file: the person
// drags it into the form's "Log or recording" box.

export const ISSUE_URL = "https://github.com/bradqui/starglance/issues/new";

export interface IssueFields {
  what: string;
  expected?: string | null;
  part?: string | null;
  agent_version?: string | null;
  game?: string | null;
}

export function issueUrl(r: IssueFields, logs: string): string {
  const what = (r.what ?? "").trim();
  let body = what;
  if (r.expected?.trim()) body += `\n\nExpected: ${r.expected.trim()}`;
  const q = new URLSearchParams({
    template: "bug_report.yml",
    title: (what.split("\n")[0] || "Problem report").slice(0, 80),
    what: body.slice(0, 1500),
    version: r.agent_version ?? "",
    part: r.part ?? "",
    game: r.game ?? "",
    logs,
  });
  return `${ISSUE_URL}?${q}`;
}
