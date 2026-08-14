export interface User {
  id: number;
  username: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Project {
  id: number;
  name: string;
  slug: string;
  description: string;
  default_branch: string;
  release_token_id: number | null;
  release_contract: string | null;
  release_name: string | null;
  created_at: string;
  updated_at: string;
  owner: User;
}

export interface Branch {
  name: string;
  is_default: boolean;
  head_commit_id: number | null;
  head_message: string;
  head_sha: string | null;
  head_author: string;
  head_date: string | null;
  commit_count: number;
  created_at: string;
}

export interface GhBranch {
  name: string;
  protected: boolean;
  sha: string;
}

export interface GhCommit {
  sha: string;
  message: string;
  author: string | null;
  date: string | null;
}

export interface DawTrack {
  name: string;
  kind: string;
  devices: string[];
}

export interface DawInfo {
  format: string;
  format_key: string;
  version: string;
  bpm: number | null;
  time_signature: string | null;
  tracks: DawTrack[];
  plugins: string[];
  samples: string[];
  extra: Record<string, unknown>;
}

export interface ProjectFile {
  path: string;
  size: number;
  blob_sha: string;
  kind: string;
  daw_format: string | null;
  daw_info: DawInfo | null;
}

export interface Tree {
  commit_id: number;
  commit_message: string;
  files: ProjectFile[];
}

export interface Commit {
  id: number;
  message: string;
  created_at: string;
  parent_id: number | null;
  author: User;
  file_count: number;
  total_size: number;
}

export interface CommitDetail extends Commit {
  files: ProjectFile[];
}

export interface DiffChange {
  kind: string;
  label: string;
  old: string | null;
  new: string | null;
}

export interface Diff {
  path: string;
  format: string | null;
  summary: DiffChange[];
  raw: string;
  binary: boolean;
  truncated: boolean;
}

export function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = bytes;
  let i = -1;
  do {
    v /= 1024;
    i++;
  } while (v >= 1024 && i < units.length - 1);
  return `${v.toFixed(1)} ${units[i]}`;
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const DAW_COLORS: Record<string, string> = {
  als: "#ff8b00",
  cpr: "#00b4ff",
  rpp: "#9b5de5",
  flp: "#39d98a",
};
