import {useEffect, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import {ArrowDown, ArrowRight, ArrowUpRight, CalendarDays, CircleHelp, Database, FlaskConical, Layers, ListChecks, Play, RefreshCw, Search, Settings2, ShieldCheck, SlidersHorizontal} from "lucide-react";
import {api, decisions, type Profile, type Results, type Saved, type Scope, scopes, type Decision, fixedDate, flatten, human} from "./model";
import {Comparison, type Filter, JobDialog, JobList, selectRows, Shortlist, type Sort} from "./vacancies";
import {Editor} from "./profile";
import {GuidedDemo, steps} from "./demo";
import "./style.css";

type View = "review" | "baseline" | "profile" | "demo";
const blankFilters: Filter = {decision: "All", search: "", country: "", mode: "", sort: "relevance", group: true};
const nav = [
  {id: "review", label: "Match review", icon: Layers},
  {id: "baseline", label: "Baseline ranking", icon: ListChecks},
  {id: "profile", label: "Candidate profile", icon: Settings2},
  {id: "demo", label: "Guided demo", icon: Play},
] as const;
const errorText = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Try again.";
const outcomes = {
  Eligible: "All required checks passed.",
  "Needs confirmation": "Ranked by relevance for follow-up. These vacancies are outside the verified shortlist.",
  Ineligible: "At least one mandatory requirement conflicts with the profile.",
  Closed: "Employer evidence confirmed these vacancies were closed.",
};

function ProfileSummary({profile, edit}: {profile: Profile; edit: () => void}) {
  return <section className="side-profile" aria-label="Saved profile summary">
    <div className="side-profile-title"><span className="avatar"><ShieldCheck size={16}/></span><div><strong>Candidate criteria</strong><small>Saved profile</small></div></div>
    <dl><div><dt>Country</dt><dd>{profile.countries.join(", ")}</dd></div>
      <div><dt>Employment</dt><dd>{profile.job_types.map(human).join(", ")}</dd></div>
      <div><dt>Duration</dt><dd>{profile.duration_months} months</dd></div></dl>
    <button className="text-button" onClick={edit}>Edit profile <ArrowRight size={14}/></button>
  </section>;
}

function ResultsList({results, baseline, filter, update, open}: {
  results: Results; baseline: boolean; filter: Filter; update: (v: Filter) => void; open: (id: string) => void;
}) {
  const pool = baseline ? results.baseline : flatten(results);
  const tabs: (Decision | "All")[] = ["All", ...decisions];
  const visible = selectRows(pool, filter);
  const countries = [...new Set(pool.map(j => j.country ?? "unknown"))].sort();
  const modes = [...new Set(pool.map(j => j.mode ?? "unknown"))].sort();
  const visibleIds = new Set(visible.map(job => job.id));
  const pairCount = filter.group ? results.duplicates.filter(w => w.kind === "probable" && w.ids.every(id => visibleIds.has(id))).length : 0;
  return <section className="panel results-panel" aria-labelledby="results-heading">
    <div className="results-heading">
      <div><h2 id="results-heading">{baseline ? "Relevance-only baseline" : filter.decision === "All" ? "All vacancies" : filter.decision}</h2>
        <p>{baseline ? "The baseline orders cards by relevance score. The status on each row shows its eligibility outcome." :
          filter.decision === "All" ? "Browse the full dataset by evidence and decision." : outcomes[filter.decision]}</p></div>
      <span className="count-label" role="status">{visible.length} of {pool.length} shown</span>
    </div>
    <div className="outcome-tabs" role="group" aria-label="Eligibility categories">{tabs.map(tab => {
      const count = tab === "All" ? pool.length : pool.filter(v => v.decision === tab).length;
      return <button key={tab} type="button" aria-pressed={filter.decision === tab}
        onClick={() => update({...filter, decision: tab})}>{tab === "All" ? "All" : tab}<span>{count}</span></button>;
    })}</div>
    <div className="filters">
      <label className="searchbox"><Search size={17}/><span className="sr-only">Search vacancies</span>
        <input type="search" placeholder="Search role, employer or location" value={filter.search} onChange={e => update({...filter, search: e.target.value})}/></label>
      <label><span className="sr-only">Filter country</span><select aria-label="Filter country" value={filter.country} onChange={e => update({...filter, country: e.target.value})}><option value="">All countries</option>
        {countries.map(v => <option key={v} value={v}>{v === "unknown" ? "Unverified country" : v}</option>)}
      </select></label>
      <label><span className="sr-only">Filter work mode</span><select aria-label="Filter work mode" value={filter.mode} onChange={e => update({...filter, mode: e.target.value})}><option value="">All work modes</option>
        {modes.map(v => <option key={v} value={v}>{human(v)}</option>)}
      </select></label>
      <label><span className="sr-only">Sort vacancies</span><select aria-label="Sort vacancies" value={filter.sort} onChange={e => update({...filter, sort: e.target.value as Sort})}><option value="relevance">Relevance score</option>
        <option value="employer">Employer A–Z</option><option value="recent">Last verified</option><option value="audit">Audit order</option>
      </select></label>
    </div>
    <div className="list-legend"><label className="check"><input type="checkbox" checked={filter.group} onChange={e => update({...filter, group: e.target.checked})}/> Group possible duplicates</label>
      {pairCount > 0 && <a href="#possible-duplicate-groups">{pairCount} {pairCount === 1 ? "group" : "groups"}</a>}
      <span>Relevance score <ArrowDown size={13}/></span>
    </div>
    {visible.length ? <JobList jobs={visible} results={results} group={filter.group} ranked={filter.sort === "relevance"} open={open}/> :
      <div className="no-results"><Search size={22}/><h3>No vacancies to show</h3><p>{filter.search || filter.country || filter.mode ? "Try a different search or clear the filters." : "This category has no vacancies in the current dataset."}</p>
        <button className="btn secondary" onClick={() => update({...blankFilters})}>Show all vacancies</button></div>}
  </section>;
}

function App() {
  const [view, setView] = useState<View>("review");
  const [scope, setScope] = useState<Scope>("audit");
  const [step, setStep] = useState(0);
  const [saved, setSaved] = useState<Saved>();
  const [profileError, setProfileError] = useState("");
  const [profileReload, setProfileReload] = useState(0);
  const [filter, setFilter] = useState<Filter>({...blankFilters, decision: "Needs confirmation"});
  const [baselineFilter, setBaselineFilter] = useState<Filter>(blankFilters);
  const [matchReload, setMatchReload] = useState(0);
  const [snapshot, setSnapshot] = useState<{key: string; result?: Results; error?: string}>();
  const [jobId, setJobId] = useState<string>();
  const [savedNotice, setSavedNotice] = useState(false);
  const [previewReference, setPreviewReference] = useState(false);
  const focusBack = useRef<HTMLElement | null>(null);
  const main = useRef<HTMLElement>(null);
  const activeScope = view === "demo" ? steps[step].scope : scope;
  const reference = view === "demo" || previewReference;
  const matchKey = `${activeScope}|${reference ? "reference" : saved?.version ?? "pending"}|${matchReload}`;
  const active = snapshot?.key === matchKey ? snapshot : undefined;
  const results = active?.result;
  const selectedJob = results && jobId ? flatten(results).find(j => j.id === jobId) : undefined;

  useEffect(() => {
    const abort = new AbortController();
    api<Saved>("/api/profile", "GET", undefined, abort.signal).then(s => {setSaved(s); setProfileError("");})
      .catch(e => {if (!abort.signal.aborted) setProfileError(errorText(e));});
    return () => abort.abort();
  }, [profileReload]);

  useEffect(() => {
    if (!reference && !saved) return;
    const abort = new AbortController();
    api<Results>(reference ? "/api/match/demo" : "/api/match", "POST", {dataset: activeScope, k: 10, as_of: fixedDate}, abort.signal)
      .then(result => {if (!abort.signal.aborted) setSnapshot({key: matchKey, result});})
      .catch(e => {if (!abort.signal.aborted) setSnapshot({key: matchKey, error: errorText(e)});});
    return () => abort.abort();
  }, [activeScope, reference, saved, matchKey]);

  function navigate(target: View) {
    setView(target);
    setJobId(undefined);
    setSavedNotice(false);
    requestAnimationFrame(() => {window.scrollTo(0,0); main.current?.focus();});
  }
  function changeScope(next: Scope, useReference = false) {
    setScope(next);
    setPreviewReference(useReference);
    setFilter({...blankFilters, decision: next === "audit" ? "Needs confirmation" : "All"});
    setBaselineFilter(blankFilters);
    setJobId(undefined);
  }
  function openVacancy(id: string) {
    if (!jobId && document.activeElement instanceof HTMLElement) focusBack.current = document.activeElement;
    setJobId(id);
  }
  function closeVacancy() {
    setJobId(undefined);
    requestAnimationFrame(() => focusBack.current?.focus());
  }
  const review = view === "review" || view === "baseline";
  return <>
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <header className="topbar">
      <a className="brand" href="#main-content" onClick={e => {e.preventDefault(); navigate("review");}}><span className="brand-icon"><Layers size={19}/></span><span>Eligibility Engine<small>Elip audit prototype</small></span></a>
      <div className="top-actions"><span className="snapshot-date"><CalendarDays size={15}/> 27 Nov 2026 snapshot</span>
        <button type="button" className="btn secondary header-demo" onClick={() => {setStep(0); navigate("demo");}}><Play size={15}/> <span>Guided demo</span></button></div>
    </header>
    <div className="shell">
      <aside className="sidebar"><nav aria-label="Main navigation">
        {nav.map(({id, label, icon: Icon}) => <button key={id} type="button" className={view === id ? "nav-link selected" : "nav-link"} onClick={() => navigate(id)} aria-current={view === id ? "page" : undefined}>
          <Icon size={18}/><span>{label}</span></button>)}
        </nav>{saved && <ProfileSummary profile={saved.profile} edit={() => navigate("profile")}/>}
      </aside>
      <main id="main-content" ref={main} tabIndex={-1}>
        <div hidden={view !== "profile"}>
          {saved && profileError && <div className="notice error" role="alert">{profileError}
            <button className="btn secondary" onClick={() => setProfileReload(i => i + 1)}>Retry profile reload</button></div>}
          {saved ? <Editor key={saved.version} saved={saved} onSaved={s => {setSaved(s); setSavedNotice(true);}}
            onReload={() => setProfileReload(v => v + 1)}/> :
            <section className="panel empty-load"><h1>Candidate profile</h1>{profileError ? <div role="alert">{profileError}<button className="btn secondary" onClick={() => setProfileReload(i => i + 1)}>Retry profile</button></div> : <p role="status">Loading candidate profile…</p>}</section>}
          {savedNotice && <div className="notice success saved-notice" role="status"><strong>Profile saved.</strong> Matching uses the updated criteria. <button className="text-button" onClick={() => navigate("review")}>View matches <ArrowRight size={14}/></button></div>}
        </div>
        {view === "demo" && <GuidedDemo step={step} setStep={setStep} results={results} open={openVacancy}
          browse={next => {changeScope(next, true); navigate("review");}}/>}
        {review && <>
          <div className="page-intro review-intro">
            <div><h1>{view === "baseline" ? "Baseline ranking" : "Match review"}</h1><p>Check which opportunities fit the candidate and which facts still need verification.</p></div>
            <div className="intro-actions">
              <label className="dataset-select"><Database size={16}/><span className="sr-only">Dataset</span><select value={scope} onChange={e => changeScope(e.target.value as Scope)}>
                {Object.entries(scopes).map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label>
              <button className="btn secondary" onClick={() => setMatchReload(v => v + 1)} disabled={!results}><RefreshCw size={15}/> Re-run</button>
            </div>
          </div>
          {scope === "synthetic" && <div className="notice synthetic"><FlaskConical size={19}/><div><strong>Synthetic test data</strong><span>These fictional vacancies demonstrate rule behavior.</span></div>
            {previewReference && <button className="text-button" onClick={() => changeScope("synthetic")}>Use saved profile <ArrowRight size={15}/></button>}</div>}
          {scope === "regression" && <div className="notice soft"><CircleHelp size={19}/><div><strong>Elip’s own posting</strong><span>Use this case to review conditional remote terms and separate stipend and conversion pay.</span></div></div>}
          {results && <>
            {view === "review" && <div className="summary-grid"><Shortlist results={results} audit={scope === "audit"} open={openVacancy}/><Comparison results={results}/></div>}
            {view === "baseline" && <div className="notice soft"><SlidersHorizontal size={19}/><div><strong>Top {results.baseline.length} relevance-ranked cards</strong><span>Compare these cards with the verified shortlist, where mandatory requirements control admission.</span></div><button className="text-button" onClick={() => navigate("review")}>Match review <ArrowUpRight size={15}/></button></div>}
            <ResultsList results={results} baseline={view === "baseline"} filter={view === "baseline" ? baselineFilter : filter}
              update={view === "baseline" ? setBaselineFilter : setFilter} open={openVacancy}/>
            <div className="data-note">{results.input_count} source cards · {results.duplicates.filter(x => x.kind === "probable").length} probable duplicate pairs · Matching uses the saved evidence snapshot</div>
          </>}
        </>}
        {view !== "profile" && !results && (active?.error || (!reference && profileError) ?
          <section className="panel empty-load" role="alert"><strong>Couldn’t load matches</strong><p>{active?.error || profileError}</p>
            <button className="btn secondary" onClick={() => {if (profileError) setProfileReload(i => i + 1); setMatchReload(i => i + 1);}}><RefreshCw size={16}/> Try again</button></section> :
          <div className="panel empty-load" role="status"><span className="spinner" aria-hidden="true"/> Loading matches…</div>)}
        {selectedJob && results && <JobDialog job={selectedJob} results={results} synthetic={activeScope === "synthetic"} onClose={closeVacancy} open={openVacancy}/>}
      </main>
    </div>
  </>;
}
createRoot(document.getElementById("root")!).render(<App/>);
