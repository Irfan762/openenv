import { useState, useCallback, useRef, useEffect } from "react";

const API = "/api/openenv";

const TASKS = [
  {
    id: "basic_format_fix",
    label: "Basic Format Fix",
    difficulty: "Easy",
    color: "text-emerald-400",
    bg: "bg-emerald-400/10 border-emerald-400/30",
    desc: "10-row product CSV: fix date formats, boolean strings, price types, category casing",
  },
  {
    id: "schema_validation",
    label: "Schema Validation",
    difficulty: "Medium",
    color: "text-amber-400",
    bg: "bg-amber-400/10 border-amber-400/30",
    desc: "15-row HR dataset: emails, phone formats, employee IDs, salary ranges, date repair",
  },
  {
    id: "deduplication_and_merge",
    label: "Deduplication & Merge",
    difficulty: "Hard",
    color: "text-rose-400",
    bg: "bg-rose-400/10 border-rose-400/30",
    desc: "16-row customer DB: 6 duplicate groups, conflict resolution, schema repair",
  },
];

const TRANSFORMS = [
  "strip", "lower", "upper", "title", "strip_title",
  "to_bool", "to_int", "to_float",
  "normalize_phone", "normalize_date",
];

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.9 ? "bg-emerald-500" : score >= 0.6 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-sm font-mono font-bold min-w-[3rem] text-right ${score >= 0.9 ? "text-emerald-400" : score >= 0.6 ? "text-amber-400" : "text-rose-400"}`}>
        {pct}%
      </span>
    </div>
  );
}

function ErrorBadge({ count }: { count: number }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold ${count === 0 ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"}`}>
      {count} {count === 1 ? "error" : "errors"}
    </span>
  );
}

function DifficultyBadge({ difficulty }: { difficulty: string }) {
  const styles: Record<string, string> = {
    Easy: "bg-emerald-400/15 text-emerald-400 border-emerald-400/30",
    Medium: "bg-amber-400/15 text-amber-400 border-amber-400/30",
    Hard: "bg-rose-400/15 text-rose-400 border-rose-400/30",
  };
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-semibold ${styles[difficulty] || ""}`}>
      {difficulty}
    </span>
  );
}

type Row = Record<string, unknown>;
type ValidationError = { row_index: number; column: string; error_type: string; message: string; current_value: unknown };
type Progress = { total_rows: number; valid_rows: number; errors_remaining: number; errors_fixed: number; duplicate_groups?: number; duplicates_resolved?: number };
type Observation = { task_id: string; dataset: Row[]; validation_errors: ValidationError[]; progress: Progress; step: number; done: boolean; message?: string };
type StepResult = { observation: Observation; reward: { value: number; explanation: string }; done: boolean };
type LogEntry = { step: number; action: string; reward: number; errorsFixed: number; explanation: string };

export default function App() {
  const [activeTask, setActiveTask] = useState(TASKS[0].id);
  const [obs, setObs] = useState<Observation | null>(null);
  const [score, setScore] = useState(0);
  const [loading, setLoading] = useState(false);
  const [episodeDone, setEpisodeDone] = useState(false);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [lastReward, setLastReward] = useState<number | null>(null);
  const [rewardFlash, setRewardFlash] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  // Action builder state
  const [actionType, setActionType] = useState("bulk_transform");
  const [rowIndex, setRowIndex] = useState(0);
  const [column, setColumn] = useState("");
  const [cellValue, setCellValue] = useState("");
  const [bulkColumn, setBulkColumn] = useState("");
  const [transform, setTransform] = useState("normalize_date");
  const [regexPattern, setRegexPattern] = useState("");
  const [regexReplacement, setRegexReplacement] = useState("");
  const [mergeIndices, setMergeIndices] = useState("");

  const doReset = useCallback(async (taskId: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId }),
      });
      const data = await res.json();
      const observation: Observation = data.observation;
      setObs(observation);
      setScore(0);
      setEpisodeDone(false);
      setLog([]);
      setLastReward(null);
      // Auto-fill first column
      if (observation.dataset.length > 0) {
        const cols = Object.keys(observation.dataset[0]);
        setColumn(cols[0] || "");
        setBulkColumn(cols[0] || "");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { doReset(activeTask); }, [activeTask]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [log]);

  const buildAction = () => {
    if (actionType === "set_value") return { type: "set_value", row_index: rowIndex, column, value: cellValue };
    if (actionType === "delete_row") return { type: "delete_row", row_index: rowIndex };
    if (actionType === "bulk_transform") return { type: "bulk_transform", column_name: bulkColumn, transform };
    if (actionType === "regex_replace") return { type: "regex_replace", column_name: bulkColumn, pattern: regexPattern, replacement: regexReplacement };
    if (actionType === "merge_rows") {
      const indices = mergeIndices.split(",").map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n));
      return { type: "merge_rows", rows_indices: indices };
    }
    return { type: "noop" };
  };

  const doStep = useCallback(async () => {
    if (!obs || episodeDone) return;
    setLoading(true);
    try {
      const action = buildAction();
      const res = await fetch(`${API}/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data: StepResult = await res.json();

      // Fetch updated score from state endpoint
      const stateRes = await fetch(`${API}/state`);
      const state = await stateRes.json();

      setObs(data.observation);
      setScore(state.score ?? 0);
      setEpisodeDone(data.done);
      setLastReward(data.reward.value);
      setRewardFlash(true);
      setTimeout(() => setRewardFlash(false), 600);

      const errFixed = obs.progress.errors_remaining - data.observation.progress.errors_remaining;
      setLog(prev => [...prev, {
        step: data.observation.step,
        action: JSON.stringify(action),
        reward: data.reward.value,
        errorsFixed: Math.max(0, errFixed),
        explanation: data.reward.explanation,
      }]);
    } finally {
      setLoading(false);
    }
  }, [obs, episodeDone, actionType, rowIndex, column, cellValue, bulkColumn, transform, regexPattern, regexReplacement, mergeIndices]);

  const columns = obs?.dataset.length ? Object.keys(obs.dataset[0]) : [];
  const errorIndex: Record<string, ValidationError> = {};
  obs?.validation_errors.forEach(e => { errorIndex[`${e.row_index}:${e.column}`] = e; });

  const taskMeta = TASKS.find(t => t.id === activeTask)!;

  return (
    <div className="min-h-screen bg-[hsl(220_16%_10%)] text-[hsl(213_31%_91%)] font-sans">
      {/* Header */}
      <header className="border-b border-white/10 bg-[hsl(220_16%_12%)] px-6 py-4">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-500/40 flex items-center justify-center text-blue-400 font-bold text-sm">OE</div>
            <div>
              <h1 className="font-bold text-white leading-none">OpenEnv DataCleaning</h1>
              <p className="text-xs text-white/40 mt-0.5">AI Agent Training Environment</p>
            </div>
          </div>
          {obs && (
            <div className="flex items-center gap-4 text-sm">
              <span className="text-white/40">Step <span className="text-white font-mono">{obs.step}</span>/50</span>
              <span className="text-white/40"><ErrorBadge count={obs.progress.errors_remaining} /></span>
              {episodeDone && (
                <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold animate-pulse">
                  Episode Complete
                </span>
              )}
            </div>
          )}
        </div>
      </header>

      <div className="max-w-screen-2xl mx-auto px-6 py-5 grid grid-cols-12 gap-5">
        {/* Left column: task picker + action panel + log */}
        <div className="col-span-4 flex flex-col gap-4">
          {/* Task selector */}
          <div className="bg-[hsl(220_16%_13%)] border border-white/8 rounded-xl p-4">
            <h2 className="text-xs font-semibold text-white/40 uppercase tracking-widest mb-3">Task</h2>
            <div className="flex flex-col gap-2">
              {TASKS.map(task => (
                <button
                  key={task.id}
                  onClick={() => { if (!loading) { setActiveTask(task.id); } }}
                  className={`text-left rounded-lg border p-3 transition-all ${activeTask === task.id ? `${task.bg} ${task.color}` : "border-white/8 hover:border-white/20 text-white/60 hover:text-white/80"}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-sm">{task.label}</span>
                    <DifficultyBadge difficulty={task.difficulty} />
                  </div>
                  <p className="text-xs opacity-70 leading-relaxed">{task.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Score panel */}
          {obs && (
            <div className={`bg-[hsl(220_16%_13%)] border rounded-xl p-4 transition-all ${rewardFlash ? "border-blue-500/60 reward-pulse" : "border-white/8"}`}>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-semibold text-white/40 uppercase tracking-widest">Score</h2>
                {lastReward !== null && (
                  <span className={`text-xs font-mono font-bold ${lastReward >= 0.55 ? "text-emerald-400" : "text-amber-400"}`}>
                    last reward: {lastReward.toFixed(3)}
                  </span>
                )}
              </div>
              <ScoreBar score={score} />
              <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                <div className="bg-white/5 rounded-lg py-2">
                  <div className="text-lg font-bold font-mono text-white">{obs.progress.valid_rows}</div>
                  <div className="text-xs text-white/40">valid rows</div>
                </div>
                <div className="bg-white/5 rounded-lg py-2">
                  <div className="text-lg font-bold font-mono text-rose-400">{obs.progress.errors_remaining}</div>
                  <div className="text-xs text-white/40">errors left</div>
                </div>
                <div className="bg-white/5 rounded-lg py-2">
                  <div className="text-lg font-bold font-mono text-emerald-400">{obs.progress.errors_fixed}</div>
                  <div className="text-xs text-white/40">fixed</div>
                </div>
              </div>
              {activeTask === "deduplication_and_merge" && (
                <div className="mt-2 grid grid-cols-2 gap-2 text-center">
                  <div className="bg-white/5 rounded-lg py-2">
                    <div className="text-lg font-bold font-mono text-white">{obs.progress.duplicate_groups ?? 0}</div>
                    <div className="text-xs text-white/40">dup groups</div>
                  </div>
                  <div className="bg-white/5 rounded-lg py-2">
                    <div className="text-lg font-bold font-mono text-emerald-400">{obs.progress.duplicates_resolved ?? 0}</div>
                    <div className="text-xs text-white/40">resolved</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Action Builder */}
          <div className="bg-[hsl(220_16%_13%)] border border-white/8 rounded-xl p-4 flex flex-col gap-3">
            <h2 className="text-xs font-semibold text-white/40 uppercase tracking-widest">Action Builder</h2>
            <select
              value={actionType}
              onChange={e => setActionType(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/60"
            >
              <option value="bulk_transform">Bulk Transform Column</option>
              <option value="set_value">Set Cell Value</option>
              <option value="delete_row">Delete Row</option>
              <option value="regex_replace">Regex Replace</option>
              <option value="merge_rows">Merge Rows (Dedup)</option>
              <option value="noop">No-op (skip)</option>
            </select>

            {actionType === "bulk_transform" && (
              <>
                <select
                  value={bulkColumn}
                  onChange={e => setBulkColumn(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/60"
                >
                  {columns.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <select
                  value={transform}
                  onChange={e => setTransform(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/60"
                >
                  {TRANSFORMS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </>
            )}

            {actionType === "set_value" && (
              <>
                <input type="number" value={rowIndex} onChange={e => setRowIndex(+e.target.value)} placeholder="Row index" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/60" />
                <select value={column} onChange={e => setColumn(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/60">
                  {columns.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <input type="text" value={cellValue} onChange={e => setCellValue(e.target.value)} placeholder="New value" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/60" />
              </>
            )}

            {actionType === "delete_row" && (
              <input type="number" value={rowIndex} onChange={e => setRowIndex(+e.target.value)} placeholder="Row index to delete" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/60" />
            )}

            {actionType === "regex_replace" && (
              <>
                <select value={bulkColumn} onChange={e => setBulkColumn(e.target.value)} className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/60">
                  {columns.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <input type="text" value={regexPattern} onChange={e => setRegexPattern(e.target.value)} placeholder="Regex pattern" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/60" />
                <input type="text" value={regexReplacement} onChange={e => setRegexReplacement(e.target.value)} placeholder="Replacement" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/60" />
              </>
            )}

            {actionType === "merge_rows" && (
              <input type="text" value={mergeIndices} onChange={e => setMergeIndices(e.target.value)} placeholder="Row indices to merge, e.g. 0,1,2" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-blue-500/60" />
            )}

            <div className="bg-white/4 rounded-lg px-3 py-2 font-mono text-xs text-white/50 break-all">
              {JSON.stringify(buildAction())}
            </div>

            <div className="flex gap-2">
              <button
                onClick={doStep}
                disabled={loading || episodeDone}
                className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-2 rounded-lg text-sm transition-colors"
              >
                {loading ? "Running..." : episodeDone ? "Done" : "Apply Action →"}
              </button>
              <button
                onClick={() => doReset(activeTask)}
                disabled={loading}
                className="px-4 bg-white/8 hover:bg-white/12 disabled:opacity-40 text-white/70 font-semibold py-2 rounded-lg text-sm transition-colors"
                title="Reset episode"
              >
                ↺
              </button>
            </div>
          </div>

          {/* Step log */}
          {log.length > 0 && (
            <div className="bg-[hsl(220_16%_13%)] border border-white/8 rounded-xl p-4">
              <h2 className="text-xs font-semibold text-white/40 uppercase tracking-widest mb-3">Step Log</h2>
              <div ref={logRef} className="flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1">
                {log.map((entry, i) => (
                  <div key={i} className="bg-white/4 rounded-lg px-3 py-2 text-xs">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-white/50 font-mono">Step {entry.step}</span>
                      <div className="flex items-center gap-2">
                        {entry.errorsFixed > 0 && <span className="text-emerald-400">-{entry.errorsFixed} errors</span>}
                        <span className={`font-mono font-bold ${entry.reward >= 0.55 ? "text-emerald-400" : "text-amber-400"}`}>r={entry.reward.toFixed(3)}</span>
                      </div>
                    </div>
                    <div className="text-white/30 font-mono truncate">{entry.action}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: dataset table + errors */}
        <div className="col-span-8 flex flex-col gap-4">
          {obs ? (
            <>
              {/* Dataset table */}
              <div className="bg-[hsl(220_16%_13%)] border border-white/8 rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/8">
                  <h2 className="text-xs font-semibold text-white/40 uppercase tracking-widest">
                    Dataset — {obs.dataset.length} rows
                  </h2>
                  <span className="text-xs text-white/30 font-mono">{taskMeta.label}</span>
                </div>
                <div className="overflow-auto max-h-[420px]">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-[hsl(220_16%_11%)] border-b border-white/8">
                      <tr>
                        <th className="px-3 py-2 text-left text-white/30 font-semibold w-8">#</th>
                        {columns.map(col => (
                          <th key={col} className="px-3 py-2 text-left text-white/50 font-semibold whitespace-nowrap">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {obs.dataset.map((row, rowIdx) => {
                        const hasError = obs.validation_errors.some(e => e.row_index === rowIdx);
                        return (
                          <tr
                            key={rowIdx}
                            className={`border-b border-white/5 transition-colors cursor-pointer ${hasError ? "hover:bg-rose-500/5" : "hover:bg-white/3"}`}
                            onClick={() => setRowIndex(rowIdx)}
                          >
                            <td className="px-3 py-1.5 text-white/25 font-mono">{rowIdx}</td>
                            {columns.map(col => {
                              const err = errorIndex[`${rowIdx}:${col}`];
                              const val = row[col];
                              const displayVal = val === null || val === undefined ? <span className="text-white/20 italic">null</span> : String(val);
                              return (
                                <td key={col} className="px-3 py-1.5 font-mono whitespace-nowrap max-w-[140px] truncate">
                                  {err ? (
                                    <span className="error-cell" title={err.message}>{displayVal}</span>
                                  ) : (
                                    <span className="text-white/75">{displayVal}</span>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Validation errors panel */}
              <div className="bg-[hsl(220_16%_13%)] border border-white/8 rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/8">
                  <h2 className="text-xs font-semibold text-white/40 uppercase tracking-widest">
                    Validation Errors
                  </h2>
                  <ErrorBadge count={obs.validation_errors.length} />
                </div>
                {obs.validation_errors.length === 0 ? (
                  <div className="px-4 py-6 text-center text-emerald-400 text-sm font-semibold">
                    All rows are valid! Episode {episodeDone ? "complete" : "— apply noop or reset"}.
                  </div>
                ) : (
                  <div className="overflow-auto max-h-60">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-[hsl(220_16%_11%)] border-b border-white/8">
                        <tr>
                          <th className="px-3 py-2 text-left text-white/30 font-semibold">Row</th>
                          <th className="px-3 py-2 text-left text-white/30 font-semibold">Column</th>
                          <th className="px-3 py-2 text-left text-white/30 font-semibold">Type</th>
                          <th className="px-3 py-2 text-left text-white/30 font-semibold">Current Value</th>
                          <th className="px-3 py-2 text-left text-white/30 font-semibold">Message</th>
                        </tr>
                      </thead>
                      <tbody>
                        {obs.validation_errors.map((err, i) => (
                          <tr key={i} className="border-b border-white/5 hover:bg-rose-500/5 cursor-pointer" onClick={() => { setRowIndex(err.row_index); setColumn(err.column); setBulkColumn(err.column); }}>
                            <td className="px-3 py-1.5 font-mono text-white/50">{err.row_index}</td>
                            <td className="px-3 py-1.5 font-mono text-blue-300">{err.column}</td>
                            <td className="px-3 py-1.5">
                              <span className="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-400 text-[10px] font-semibold uppercase">{err.error_type}</span>
                            </td>
                            <td className="px-3 py-1.5 font-mono text-rose-300 max-w-[120px] truncate">{String(err.current_value ?? "null")}</td>
                            <td className="px-3 py-1.5 text-white/40 max-w-[240px] truncate">{err.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Status message */}
              {obs.message && (
                <div className="bg-blue-500/8 border border-blue-500/20 rounded-xl px-4 py-3 text-xs text-blue-300">
                  {obs.message}
                </div>
              )}
            </>
          ) : (
            <div className="col-span-8 flex items-center justify-center h-64 text-white/30">
              {loading ? "Loading environment..." : "Select a task to begin"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
