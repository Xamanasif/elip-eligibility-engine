import {ArrowLeft, ArrowRight, ArrowUpRight, CircleCheck, FlaskConical} from "lucide-react";
import {type Results, location, flatten, type Scope} from "./model";
import {Badge} from "./vacancies";

export const steps: {company: string; title: string; ids: string[]; scope: Scope; text: string}[] = [
  {company: "Infineon", title: "Country requirement catches five mismatches", ids: ["A23", "A24", "A25", "A26", "A28"], scope: "audit",
    text: "The candidate requested India-based roles. These five on-site listings are in Malaysia, so their relevance scores cannot move them into the shortlist."},
  {company: "Agoda", title: "Official status takes priority", ids: ["A10"], scope: "audit",
    text: "Elip still displayed Apply. The employer’s official vacancy path explicitly confirmed it was closed during the audit."},
  {company: "Celonis", title: "The job type must fit", ids: ["A05"], scope: "audit",
    text: "The recommendation appeared as an internship. Employer evidence identified it as a full-time graduate role starting 1 February 2027."},
  {company: "Google", title: "Academic stage and possible duplication", ids: ["A01", "A02"], scope: "audit",
    text: "The indexed employer listing required penultimate-year enrolment. The two Google cards remain separate because a shared requisition ID was not verified."},
  {company: "CommerceIQ", title: "An open signal still leaves questions", ids: ["A19", "A20"], scope: "audit",
    text: "The employer board listed two distinct Bengaluru roles. The audit did not verify their dates and full requirements, so both remain in Needs confirmation."},
  {company: "Synthetic", title: "A fully verified fixture reaches the shortlist", ids: ["S01"], scope: "synthetic",
    text: "This is a fictional vacancy with complete test evidence. The fixed demo profile passes every required check, so the fixture appears in the verified shortlist."},
];

export function GuidedDemo({step, setStep, results, open, browse}: {
  step: number; setStep: (n: number) => void; results?: Results; open: (id: string) => void; browse: (s: Scope) => void;
}) {
  const current = steps[step];
  const rows = results ? flatten(results).filter(v => current.ids.includes(v.id)) : [];
  return <div className="demo-page">
    <div className="page-intro"><h1>Guided demo</h1><p>Six cases using the fixed reference profile. Your saved profile is separate.</p></div>
    <div className="demo-grid">
      <nav className="panel demo-nav" aria-label="Demo steps">{steps.map((s, i) =>
        <button key={s.company} className={i === step ? "selected" : ""} aria-current={i === step ? "step" : undefined} onClick={() => setStep(i)}>
          <span>{i + 1}</span>{s.company}<ArrowRight size={15}/>
        </button>)}</nav>
      <section className="panel demo-case" aria-labelledby="demo-case-title">
        <span className={`demo-type ${current.scope === "synthetic" ? "synthetic" : ""}`}>
          {current.scope === "synthetic" ? <FlaskConical size={15}/> : <CircleCheck size={15}/>}
          {current.scope === "synthetic" ? "Synthetic test fixture" : "Real audit evidence"}
        </span>
        <h2 id="demo-case-title">{current.title}</h2><p>{current.text}</p>
        <div className="demo-records">{rows.map(job => <div key={job.id}>
          <div><span className="eyebrow">{job.id} · {job.employer}</span>
            <button className="job-title" onClick={() => open(job.id)}>{job.title}</button><p className="muted">{location(job)}</p></div>
          <Badge decision={job.decision}/>
        </div>)}</div>
        <div className="demo-controls">
          <button className="btn secondary" disabled={step === 0} onClick={() => setStep(step - 1)}><ArrowLeft size={16}/> Previous</button>
          {step < steps.length - 1 ?
            <button className="btn primary" onClick={() => setStep(step + 1)}>Next case <ArrowRight size={16}/></button> :
            <button className="btn primary" onClick={() => browse("synthetic")}>Open synthetic matches <ArrowUpRight size={16}/></button>}
        </div>
      </section>
    </div>
  </div>;
}
