import {useId, useRef, useState} from "react";
import {Plus, X, Check, RefreshCw} from "lucide-react";
import {api, ApiError, type Degree, human, type Profile, type Saved} from "./model";

const workModes = ["onsite", "hybrid", "remote", "conditional_remote"];
const jobTypes = ["internship", "full_time", "contract", "part_time"];
const cityOptions = ["Bengaluru", "Chennai", "Delhi", "Goa", "Gurugram", "Hyderabad", "Mumbai", "Noida", "Pune"];
const skills = ["CI", "Docker", "FastAPI", "Java", "LangGraph", "LLMs", "NumPy", "Python", "RAG", "React", "SQL", "TypeScript", "forecasting"];
const roles = ["AI engineering", "backend engineering", "data analytics", "data engineering", "data science", "machine learning", "product management", "software engineering"];
const countryLabel = new Intl.DisplayNames(["en"], {type: "region", fallback: "code"});
const countryName = (code: string) => {
  try {return `${countryLabel.of(code)} (${code})`;} catch {return code;}
};

const numberInput = (value: number | null) => value !== null && Number.isFinite(value) ? value : "";

function Chips({title, description, values, change, options, free = false, label = human, country = false}: {
  title: string; description?: string; values: string[]; change: (v: string[]) => void; options: string[];
  free?: boolean; label?: (v: string) => string; country?: boolean;
}) {
  const id = useId();
  const [input, setInput] = useState("");
  const [feedback, setFeedback] = useState("");
  const control = useRef<HTMLInputElement | HTMLSelectElement | null>(null);
  function add(raw: string) {
    const item = country ? raw.trim().toUpperCase() : raw.trim();
    if (!item) return;
    if (country && !/^[A-Z]{2}$/.test(item)) {
      setFeedback("Use a two-letter country code, such as IN.");
      return;
    }
    if (values.some(v => v.toLowerCase() === item.toLowerCase())) {
      setFeedback(`${label(item)} is already selected.`);
      return;
    }
    change([...values, item]);
    setInput("");
    setFeedback("");
    control.current?.focus();
  }
  return <div className="chip-field">
    <label className="field-label" htmlFor={id}>{title}</label>
    {description && <p className="field-note" id={id + "-note"}>{description}</p>}
    <div className="chips" aria-label={title + " selected"}>
      {values.map(v => <span className="chip" key={v}>{label(v)}
        <button type="button" className="chip-remove" aria-label={`Remove ${label(v)} from ${title}`}
          onClick={() => {change(values.filter(x => x !== v)); setFeedback(""); control.current?.focus();}}><X size={13}/></button>
      </span>)}
    </div>
    <div className="chip-entry">
      {free ? <>
        <input id={id} ref={node => {control.current = node;}} aria-describedby={description ? id + "-note" : undefined}
          value={input} onChange={e => {setInput(e.target.value); setFeedback("");}} list={id + "-options"} maxLength={country ? 2 : 80}
          placeholder={country ? "Country code" : "Choose or type an item"}
          onKeyDown={e => {if (e.key === "Enter") {e.preventDefault(); add(input);}}}/>
        <datalist id={id + "-options"}>{options.filter(v => !values.includes(v)).map(v => <option key={v} value={v}>{label(v)}</option>)}</datalist>
        <button type="button" className="btn secondary add-chip" aria-label={`Add to ${title}`} onClick={() => add(input)} disabled={!input.trim()}><Plus size={16}/><span>Add</span></button>
      </> : <select id={id} ref={node => {control.current = node;}} value="" onChange={e => add(e.target.value)}>
        <option value="">Select an option</option>
        {options.filter(v => !values.includes(v)).map(v => <option key={v} value={v}>{label(v)}</option>)}
      </select>}
    </div>
    {feedback && <p className="field-note" role="status">{feedback}</p>}
  </div>;
}

export function Editor({saved, onSaved, onReload}: {saved: Saved; onSaved: (s: Saved) => void; onReload: () => void}) {
  const [draft, setDraft] = useState(saved.profile);
  const [degrees, setDegrees] = useState(() => saved.profile.degrees.map((degree, i) => ({id: i, degree})));
  const nextDegree = useRef(degrees.length);
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<{text: string; conflict: boolean} | null>(null);
  function change<K extends keyof Profile>(k: K, value: Profile[K]) {setDraft(p => ({...p, [k]: value}));}
  function updateDegree(id: number, value: Partial<Degree>) {
    setDegrees(previous => previous.map(row => row.id === id ? {...row, degree: {...row.degree, ...value}} : row));
  }
  const draftProfile = {...draft, degrees: degrees.map(row => row.degree)};
  const dirty = JSON.stringify(draftProfile) !== JSON.stringify(saved.profile);
  function resetDraft() {
    setDraft(saved.profile);
    setDegrees(saved.profile.degrees.map((degree, index) => ({id: nextDegree.current + index, degree})));
    nextDegree.current += saved.profile.degrees.length;
    setFailure(null);
  }
  return <div className="profile-page">
    <div className="page-intro">
      <h1>Candidate profile</h1><p>Hard requirements determine eligibility. Preferences influence relevance scores.</p>
    </div>
    <form onSubmit={async e => {
      e.preventDefault();
      setFailure(null);
      setSaving(true);
      try {
        const profile = {...draftProfile, degrees: draftProfile.degrees.map(d => ({...d, field: d.field?.trim() || null}))};
        onSaved(await api<Saved>("/api/profile", "PUT", {version: saved.version, profile}));
      } catch (error) {
        setFailure({text: error instanceof Error ? error.message : "The profile could not be saved.",
          conflict: error instanceof ApiError && error.status === 409});
      } finally {setSaving(false);}
    }}>
      <div className="profile-grid">
        <section className="panel form-panel" aria-labelledby="requirements-heading">
          <h2 id="requirements-heading">Hard requirements</h2>
          <div className="field-grid">
            <Chips title="Allowed countries" description="Use two-letter country codes." values={draft.countries} change={v => change("countries", v)} options={["IN", "GB", "MY", "SG", "US", "DE", "CA"]} free country label={countryName}/>
            <Chips title="Allowed cities" description="Leave empty to allow any city in the selected countries." values={draft.cities} change={v => change("cities", v)} options={cityOptions} free/>
            <Chips title="Allowed work modes" values={draft.modes} change={v => change("modes", v)} options={workModes}/>
            <Chips title="Allowed employment types" values={draft.job_types} change={v => change("job_types", v)} options={jobTypes}/>
          </div>
          <h3>Availability</h3>
          <div className="field-grid">
            <label>Earliest start<input type="date" value={draft.start_from} required onChange={e => change("start_from", e.target.value)}/></label>
            <label>Latest start<input type="date" value={draft.start_to} required min={draft.start_from} onChange={e => change("start_to", e.target.value)}/></label>
            <label>Available until<input type="date" value={draft.available_until ?? ""} min={draft.start_to} onChange={e => change("available_until", e.target.value || null)}/></label>
            <label>Duration (months)<input type="number" value={numberInput(draft.duration_months)} min={1} max={36} required onChange={e => change("duration_months", e.target.valueAsNumber)}/></label>
          </div>
        </section>
        <section className="panel form-panel" aria-labelledby="education-heading">
          <h2 id="education-heading">Education and experience</h2>
          <div className="field-grid">
            <label>Academic stage<select value={draft.academic_stage} onChange={e => change("academic_stage", e.target.value)}>
              {["penultimate", "final_year", "graduate", "other"].map(v => <option key={v} value={v}>{human(v)}</option>)}
            </select></label>
            <label>Graduation year<input type="number" value={numberInput(draft.graduation_year)} min={2000} max={2100} required onChange={e => change("graduation_year", e.target.valueAsNumber)}/></label>
            <label>Internship experience (months)<input type="number" value={numberInput(draft.internship_months)} min={0} required onChange={e => change("internship_months", e.target.valueAsNumber)}/></label>
            <label>Industry experience (months)<input type="number" value={numberInput(draft.industry_months)} min={0} required onChange={e => change("industry_months", e.target.valueAsNumber)}/></label>
            <label>Equivalent experience (months)<input type="number" value={numberInput(draft.equivalent_months)} min={0} onChange={e => change("equivalent_months", e.target.value === "" ? null : e.target.valueAsNumber)}/></label>
            <label>Curriculum placement<select value={String(draft.curricular_internship)} onChange={e => change("curricular_internship", e.target.value === "null" ? null : e.target.value === "true")}><option value="null">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label>
          </div>
          <h3>Degrees</h3>
          {degrees.map(({id, degree}, index) => <fieldset className="degree" key={id}>
            <legend>Degree {index + 1}</legend>
            <div className="field-grid">
              <label>Degree level<select value={degree.level} onChange={e => updateDegree(id, {level: e.target.value})}>
                {["bachelors", "masters", "doctorate", "other"].map(v => <option key={v} value={v}>{human(v)}</option>)}
              </select></label>
              <label>Field of study<input value={degree.field ?? ""} placeholder="Leave empty if unknown" onChange={e => updateDegree(id, {field: e.target.value || null})}/></label>
            </div>
            <div className="degree-actions"><label className="check"><input type="checkbox" checked={degree.completed} onChange={e => updateDegree(id, {completed: e.target.checked})}/>Completed</label>
              <button type="button" className="text-button" aria-label={`Remove degree ${index + 1}`} onClick={() => setDegrees(previous => previous.filter(row => row.id !== id))}><X size={15}/> Remove</button>
            </div>
          </fieldset>)}
          <button type="button" className="btn secondary" onClick={() => {
            const id = nextDegree.current++;
            setDegrees(previous => [...previous, {id, degree: {level: "bachelors", field: null, completed: false}}]);
          }}><Plus size={16}/> Add degree</button>
        </section>
        <section className="panel form-panel profile-wide" aria-labelledby="pref-heading">
          <h2 id="pref-heading">Ranking preferences</h2>
          <div className="field-grid preferences">
            <Chips title="Preferred roles" values={draft.roles} change={v => change("roles", v)} options={roles} free/>
            <Chips title="Skills" description="Skills are also checked against mandatory listing requirements." values={draft.skills} change={v => change("skills", v)} options={skills} free/>
            <Chips title="Preferred cities" values={draft.preferred_cities} change={v => change("preferred_cities", v)} options={cityOptions} free/>
            <Chips title="Preferred work modes" values={draft.preferred_modes} change={v => change("preferred_modes", v)} options={workModes}/>
            <label>Expected monthly stipend (INR)<input type="number" value={numberInput(draft.expected_stipend_inr)} min={0} onChange={e => change("expected_stipend_inr", e.target.value === "" ? null : e.target.valueAsNumber)}/></label>
          </div>
        </section>
      </div>
      <div className="form-footer">
        <span className="muted">{dirty ? "Unsaved changes" : "Preferences saved"}</span>
        <div className="form-actions"><button type="button" className="btn secondary" disabled={saving || !dirty} onClick={resetDraft}>Discard changes</button>
        <button type="submit" className="btn primary" disabled={saving || !dirty}><Check size={16}/>{saving ? "Saving…" : "Save profile"}</button></div>
      </div>
      {failure && <div className="notice error" role="alert">{failure.text}
        {failure.conflict && <button type="button" className="btn secondary" onClick={onReload}><RefreshCw size={15}/> Reload saved profile and discard edits</button>}</div>}
    </form>
  </div>;
}
