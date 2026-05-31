export type AnalysisType = "analyze" | "compare" | "batch";

export interface SavedDataset {
  id: string;
  type: AnalysisType;
  label: string;       // filename, "ref vs cur", or "N files"
  jobId: string;       // primary job id (for batch: first job id)
  href: string;        // navigation target
  createdAt: number;
}

const KEY = "emd_datasets";

export function getSavedDatasets(): SavedDataset[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function saveDataset(ds: Omit<SavedDataset, "id" | "createdAt">): SavedDataset {
  const saved = getSavedDatasets();
  const entry: SavedDataset = { ...ds, id: Math.random().toString(36).slice(2), createdAt: Date.now() };
  // Deduplicate by jobId
  const filtered = saved.filter((s) => s.jobId !== ds.jobId);
  localStorage.setItem(KEY, JSON.stringify([entry, ...filtered].slice(0, 50)));
  window.dispatchEvent(new Event("emd_storage"));
  return entry;
}

export function removeDataset(id: string): void {
  const saved = getSavedDatasets().filter((s) => s.id !== id);
  localStorage.setItem(KEY, JSON.stringify(saved));
  window.dispatchEvent(new Event("emd_storage"));
}
