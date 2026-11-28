import {useEffect, useRef} from "react";
import {ArrowRight, ArrowUpRight, ChevronRight, CircleCheck, ClipboardList, ExternalLink, Link2, MapPin, X} from "lucide-react";
import {decisions, exceptions, type Decision, type Results, human, location, nextStep, ordinal, rank, ruleName, rules, tone, type Vacancy} from "./model";

export type Sort = "relevance" | "employer" | "recent" | "audit";
export type Filter = {decision: Decision | "All"; country: string; mode: string; search: string; sort: Sort; group: boolean};
const sortRows: Record<Sort, (a: Vacancy, b: Vacancy) => number> = {
  relevance: rank,
  employer: (a, b) => a.employer.localeCompare(b.employer) || a.title.localeCompare(b.title),
  recent: (a, b) => (b.verified_at ?? "").localeCompare(a.verified_at ?? "") || rank(a,b),
  audit: (a, b) => a.id.localeCompare(b.id),
};

export function selectRows(jobs: Vacancy[], filter: Filter) {
  const query = filter.search.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return jobs.filter(job => {
    const searchable = [job.id, job.employer, job.title, job.req_id, location(job), ...job.skills, ...exceptions(job).map(ruleName)]
      .join(" ").toLowerCase();
    return (filter.decision === "All" || filter.decision === job.decision)
      && (!filter.country || filter.country === (job.country ?? "unknown"))
      && (!filter.mode || filter.mode === (job.mode ?? "unknown"))
      && query.every(term => searchable.includes(term));
  }).sort(sortRows[filter.sort]);
}

export function Badge({decision}: {decision: Decision}) {
  return <span className={`badge ${tone[decision]}`}><i aria-hidden="true"/>{decision}</span>;
}

export function Comparison({results}: {results: Results}) {
  const series = [
    {label: "Relevance-only baseline", count: results.baseline.length,
      counts: decisions.map(d => results.baseline.filter(j => j.decision === d).length)},
    {label: "Eligibility review · full dataset", count: results.input_count,
      counts: decisions.map(d => results.groups[d].length)},
  ];
  return <section className="panel comparison" aria-labelledby="comparison-title">
    <div className="section-heading"><div><h2 id="comparison-title">Decision breakdown</h2><p>Compare the top baseline picks with outcomes across the full dataset.</p></div><ClipboardList size={19} aria-hidden="true"/></div>
    {series.map(({label, count, counts}) => <div className="chart-row" key={label} role="img"
      aria-label={`${label}, ${count} cards. ${decisions.map((d, i) => `${d}: ${counts[i]}`).join(", ")}`}>
      <div className="chart-label"><span>{label}</span><strong>{count} cards</strong></div>
      <div className="bar" aria-hidden="true">{counts.map((n,i) => n > 0 && <span className={tone[decisions[i]]} key={decisions[i]} style={{width: `${n / count * 100}%`}}>{n}</span>)}</div>
    </div>)}
    <div className="chart-key">{decisions.map(d => <span key={d}><i className={tone[d]}/>{d === "Ineligible" ? "Confirmed exclusions" : d}</span>)}</div>
  </section>;
}

function JobRow({job, open, position, related}: {job: Vacancy; open: (id: string) => void; position?: number; related: boolean}) {
  const gaps = exceptions(job);
  const shown = gaps.sort((a,b) => Number(b.result === "fail") - Number(a.result === "fail"));
  const initials = job.employer.trim().split(/[\s.]+/).slice(0, 2).map(word => word[0]).join("").toUpperCase();
  return <article className="job-row">
    {position !== undefined && <span className="row-rank" aria-label={`Rank ${position}`}>{ordinal(position)}</span>}
    <div className="job-main">
      <span aria-hidden="true" className="company-mark">{initials}</span>
      <div className="job-copy">
        <div className="job-company">{job.employer}{related && <span className="related-label"><Link2 size={12}/> Possible duplicate</span>}</div>
        <button className="job-title" type="button" onClick={() => open(job.id)}>{job.title}</button>
        <div className="job-meta"><span><MapPin size={13}/>{location(job)}</span>{job.mode && <span>{human(job.mode)}</span>}</div>
      </div>
    </div>
    <div className="job-summary">
      <Badge decision={job.decision}/>
      <p>{gaps.length ? shown.slice(0, 2).map(ruleName).join(" · ") : "Required checks passed"}{gaps.length > 2 && <span className="muted"> +{gaps.length - 2}</span>}</p>
    </div>
    <div className="job-end"><span className="score" title="Relevance score">{job.score.toFixed(3)}</span>
      <button className="btn icon subtle" aria-label={`Review ${job.title} at ${job.employer}`} onClick={() => open(job.id)}><ChevronRight size={18}/></button>
    </div>
  </article>;
}

export function JobList({jobs, results, group, ranked, open}: {
  jobs: Vacancy[]; results: Results; group: boolean; ranked: boolean; open: (id: string) => void;
}) {
  const warnings = results.duplicates.filter(d => d.kind === "probable");
  const selected = new Map(jobs.map(job => [job.id, job]));
  const relatedIds = new Set(warnings.flatMap(w => w.ids));
  const visiblePairs = group ? warnings.filter(w => w.ids.every(id => selected.has(id))) : [];
  return <div className="job-list">
    {jobs.map((job, i) => <JobRow key={job.id} job={job} open={open}
      position={ranked ? i + 1 : undefined} related={relatedIds.has(job.id)}/>)}
    {!!visiblePairs.length && <div className="duplicate-groups" id="possible-duplicate-groups" tabIndex={-1}>
      <h3>Possible duplicate groups</h3>
      {visiblePairs.map(pair => <section className="duplicate-group" key={pair.ids.join("/")}
        aria-label={`Possible duplicate group for ${selected.get(pair.ids[0])?.employer}`}>
        <div className="duplicate-heading"><Link2 size={15}/> Possible duplicates <span>Two separate vacancy records</span></div>
        <ul className="pair-links">{pair.ids.map(id => {
          const job = selected.get(id)!;
          return <li key={id}><button className="text-button" onClick={() => open(id)}>
            {job.id} · {job.employer}<ArrowRight size={13}/></button><Badge decision={job.decision}/></li>;
        })}</ul>
      </section>)}
    </div>}
  </div>;
}

export function Shortlist({results, audit, open, reviewUnresolved}: {
  results: Results; audit: boolean; open: (id: string) => void; reviewUnresolved: () => void;
}) {
  const unknown = results.groups["Needs confirmation"];
  const missing = new Set(unknown.flatMap(job => exceptions(job).map(r => r.code)));
  const examples = [
    [["STATUS_UNVERIFIED", "STATUS_CONFLICT", "STATUS_STALE"], "whether applications are open"],
    [["START_WINDOW", "AVAILABLE_UNTIL", "DURATION"], "internship dates and duration"],
    [["REQUIREMENTS_INCOMPLETE"], "mandatory employer requirements"],
  ].filter(([codes]) => Array.isArray(codes) && codes.some(code => missing.has(code))).map(([, label]) => label);
  return <section className="panel shortlist" aria-labelledby="shortlist-title">
    <div className="section-heading"><div><h2 id="shortlist-title">Verified shortlist</h2><p>Ranked vacancies that pass all mandatory checks.</p></div><CircleCheck size={20} aria-hidden="true"/></div>
    {results.eligible.length ? <JobList jobs={results.eligible} results={results} group={false} ranked open={open}/> :
      <div className="shortlist-empty"><div className="shortlist-count">0<span> verified vacancies</span></div>
        <p>{audit && unknown.length ? "No real audit vacancy had enough verified information to pass every mandatory check." :
          "No vacancy passes every mandatory check with the current criteria."}</p>
        {!!examples.length && <p className="muted">Examples to check include {new Intl.ListFormat("en").format(examples as string[])}.</p>}
        {unknown.length > 0 && <button type="button" className="text-button shortlist-link" onClick={reviewUnresolved}>
          Review {unknown.length} unresolved <ArrowRight size={15}/>
        </button>}
      </div>}
  </section>;
}

export function JobDialog({job, results, synthetic, onClose, open}: {
  job: Vacancy; results: Results; synthetic: boolean; onClose: () => void; open: (id: string) => void;
}) {
  const node = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const dialog = node.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  useEffect(() => {heading.current?.focus(); if (node.current) node.current.scrollTop = 0;}, [job.id]);
  const problems = exceptions(job);
  const passes = job.reasons.filter(r => r.result === "pass");
  const siblingIds = new Set(results.duplicates.filter(w => w.ids.includes(job.id))
    .flatMap(w => w.ids).filter(id => id !== job.id));
  const related = decisions.flatMap(d => results.groups[d]).filter(v => siblingIds.has(v.id));
  return <dialog ref={node} className="job-dialog" aria-labelledby="job-dialog-title"
    onCancel={e => {e.preventDefault(); onClose();}} onClick={e => {if (e.target === node.current) {
      const box = node.current.getBoundingClientRect();
      if (e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom) onClose();
    }}}>
    <div className="dialog-header">
      <span className="eyebrow">{synthetic ? "Synthetic vacancy" : "Vacancy details"} · {job.id}</span>
      <button className="btn icon secondary" type="button" aria-label="Close vacancy details" onClick={onClose}><X size={19}/></button>
    </div>
    <div className="dialog-content">
      <Badge decision={job.decision}/><h2 id="job-dialog-title" tabIndex={-1} ref={heading}>{job.title}</h2>
      <p className="muted">{job.employer} · {location(job)}{job.mode ? " · " + human(job.mode) : ""}</p>
      <dl className="facts">
        <div><dt>Relevance score</dt><dd>{job.score.toFixed(3)}</dd></div>
        <div><dt>Employment</dt><dd>{job.job_type ? human(job.job_type) : "Unverified"}</dd></div>
        <div><dt>Source status</dt><dd>{human(job.status)}{job.verified_at && <small>{job.verified_at}</small>}</dd></div>
        <div><dt>Requisition</dt><dd>{job.req_id ?? "Unverified"}</dd></div>
      </dl>
      <div className="next-step"><ArrowRight size={18}/><div><strong>Recommended next step</strong><p>{nextStep(job)}</p></div></div>
      <section className="dialog-section"><h3>Eligibility checks</h3>
        {problems.length === 0 ? <p>All required checks passed for the selected profile.</p> :
          <ul className="check-list">{problems.map(r => <li key={r.code}>
            <div><strong>{ruleName(r)}</strong><span className={`flag ${r.result}`}>{r.result === "fail" ? "Doesn’t meet requirement" : "Needs verification"}</span></div>
            <p>{r.code === "EMPLOYMENT_TYPE" ? human(r.value) : r.value}</p>
            {rules[r.code]?.[1] && <p className="muted">{rules[r.code][1]}</p>}
            {!synthetic && <a href={r.evidence_url} target="_blank" rel="noreferrer">View supporting source <ArrowUpRight size={13}/></a>}
          </li>)}</ul>}
        {!!passes.length && <details className="passed-checks"><summary>{passes.length} checks passed</summary><ul>{passes.map(r => <li key={r.code}>{ruleName(r)} · {human(r.value)}</li>)}</ul></details>}
      </section>
      {!!job.compensation.length && <section className="dialog-section"><h3>Compensation</h3><ul className="check-list">
        {job.compensation.map((pay,i) => <li key={i}><strong>{human(pay.stage)}</strong><p>{pay.currency} {pay.amount.toLocaleString("en-IN")} / {pay.period}{pay.conditional ? " · Conditional on conversion" : ""}</p></li>)}
      </ul></section>}
      {related.length > 0 && <section className="dialog-section"><h3>Related vacancy records</h3><p className="muted">Possible duplicates stay separate and keep their own decision and evidence.</p>
        <ul className="related-list">{related.map(other => <li key={other.id}><button className="text-button" onClick={() => open(other.id)}>{other.id} · {other.title} <ArrowRight size={15}/></button><Badge decision={other.decision}/></li>)}</ul>
      </section>}
      <section className="dialog-section"><h3>Source evidence</h3><ol className="evidence-list">
        {job.evidence.map((note, i) => <li key={i}><span className="eyebrow">{note.date}</span><p>{note.note}</p>
          {!synthetic && <a href={note.url} target="_blank" rel="noreferrer">Open source <ExternalLink size={13}/></a>}</li>)}
      </ol></section>
    </div>
  </dialog>;
}
