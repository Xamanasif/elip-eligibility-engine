export const decisions = ["Eligible", "Needs confirmation", "Ineligible", "Closed"] as const;
export type Decision = typeof decisions[number];
export type Scope = "audit" | "synthetic" | "regression";
export type Degree = {level: string; field: string | null; completed: boolean};
export type Profile = {
  start_from: string; start_to: string; available_until: string | null; duration_months: number;
  countries: string[]; roles: string[]; modes: string[]; skills: string[];
  job_types: string[]; cities: string[]; expected_stipend_inr: number | null;
  academic_stage: string; graduation_year: number; degrees: Degree[];
  industry_months: number; internship_months: number; equivalent_months: number | null;
  curricular_internship: boolean | null; preferred_cities: string[]; preferred_modes: string[];
};
export type Saved = {version: number; profile: Profile};
export type Reason = {code: string; result: "pass" | "fail" | "unknown"; value: string; evidence_url: string};
export type Evidence = {url: string; date: string; note: string};
export type Vacancy = {
  id: string; employer: string; title: string; cities: string[]; country: string | null;
  mode: string | null; job_type: string | null; score: number; decision: Decision;
  status: string; verified_at: string | null; req_id: string | null; provider: string | null;
  source_url: string; elip_apply_url: string | null; reasons: Reason[]; evidence: Evidence[]; skills: string[];
  compensation: {stage: string; currency: string; amount: number; period: string; conditional: boolean}[];
  exact_duplicate_of: string | null;
};
export type Results = {
  input_count: number; k: number; profile_version: number | null; baseline: Vacancy[]; eligible: Vacancy[];
  groups: Record<Decision, Vacancy[]>; duplicates: {kind: "exact" | "probable"; ids: string[]}[];
};
export const scopes: Record<Scope, string> = {
  audit: "Real audit · 31 cards", synthetic: "Synthetic · test fixtures", regression: "Elip posting · regression",
};
export const fixedDate = "2026-11-27";
export const tone: Record<Decision, string> = {
  Eligible: "green", "Needs confirmation": "amber", Ineligible: "rose", Closed: "slate",
};
export const labels: Record<string, string> = {
  onsite: "On-site", hybrid: "Hybrid", remote: "Remote", conditional_remote: "Conditional remote",
  internship: "Internship", full_time: "Full-time", part_time: "Part-time", contract: "Contract",
  penultimate: "Penultimate year", final_year: "Final year", graduate: "Graduate", other: "Other",
  bachelors: "Bachelor’s", masters: "Master’s", doctorate: "Doctorate",
  stipend: "Internship stipend", conversion_base: "PPO base salary", conversion_ctc: "PPO total compensation",
  conversion_equity: "PPO equity",
};
export const human = (value: string) => labels[value] ?? value.replaceAll("_", " ");
export const location = (job: Vacancy) => [...job.cities, job.country].filter(Boolean).join(", ") || "Location unverified";
export const ordinal = (x: number) => String(x).padStart(2, "0");
export const rank = (a: Vacancy, b: Vacancy) => b.score - a.score || a.id.localeCompare(b.id);
export const flatten = (r: Results) => decisions.flatMap(x => r.groups[x]);

export const rules: Record<string, [name: string, next: string]> = {
  VACANCY_CLOSED: ["Vacancy closed", "Look for a new requisition on the employer’s careers site."],
  STATUS_CONFLICT: ["Conflicting status sources", "Check the exact requisition on the employer’s application system."],
  STATUS_UNVERIFIED: ["Opening status unverified", "Confirm that the official posting still accepts applications."],
  STATUS_STALE: ["Verification is stale", "Recheck the employer link and record when it was checked."],
  STATUS_OPEN: ["Open status checked", ""],
  EMPLOYMENT_TYPE: ["Employment type", "Check whether the employer offers an internship under this requisition."],
  REMOTE_PERMISSION: ["Remote work eligibility", "Ask which countries qualify and whether remote work requires approval."],
  COUNTRY: ["Work country", "Look for a vacancy that supports a country in the candidate’s criteria."],
  CITY: ["Work city", "Confirm the office location or look for an eligible city."],
  WORK_MODE: ["Work arrangement", "Check the official work arrangement and any office attendance requirement."],
  ACADEMIC_STAGE: ["Academic stage", "Check the posting’s required academic stage before applying."],
  GRADUATION_YEAR: ["Graduation year", "Verify the accepted graduation year with the employer."],
  DEGREE: ["Degree requirements", "Confirm the accepted degree level and subject with the employer."],
  CURRICULUM: ["Academic placement", "Confirm with your college whether the placement is part of your curriculum."],
  EXPERIENCE: ["Experience requirements", "Confirm which experience the employer counts toward the minimum."],
  MANDATORY_SKILL: ["Required skills", "Check the skills named as mandatory in the official listing."],
  START_WINDOW: ["Start date", "Request the exact start date and compare it with the availability window."],
  DURATION: ["Internship duration", "Confirm the contract length with the employer."],
  AVAILABLE_UNTIL: ["End date", "Confirm the final working date fits your availability."],
  REQUIREMENTS_INCOMPLETE: ["Full screening criteria", "Ask the employer for the full mandatory screening criteria."],
};
export const ruleName = (reason: Reason) => rules[reason.code]?.[0] ?? human(reason.code.toLowerCase());
export const exceptions = (job: Vacancy) => job.reasons.filter(r => r.result === "fail" || r.result === "unknown");
export function nextStep(job: Vacancy) {
  const reason = exceptions(job).find(r => r.result === "fail") ?? exceptions(job)[0];
  return reason ? rules[reason.code]?.[1] || "Check this requirement against the employer’s latest posting."
    : "Review the source and confirm details before applying.";
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {super(message);}
}
export async function api<T>(url: string, method = "GET", payload?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {method, signal, headers: {"Content-Type": "application/json"},
    body: payload === undefined ? undefined : JSON.stringify(payload)});
  const data = await response.json().catch(() => null);
  if (!response.ok || data === null) {
    const detail = data?.detail;
    const messages = Array.isArray(detail) ? detail.map((d: {loc: string[]; msg: string}) =>
      d.loc.filter(x => x !== "body" && x !== "profile").join(" / ") + " · " + d.msg).join(" ") : detail;
    throw new ApiError(messages || `Request failed (${response.status}). Try again.`, response.status);
  }
  return data;
}
