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

export interface ReviewComment {
  id: number;
  version_id: number;
  time_s: number;
  body: string;
  resolved: boolean;
  author_name: string;
  parent_id: number | null;
  created_at: string;
  status: string;
  fixed_in: number | null;
  verified_at: string | null;
  voice_format: string;
  voice_duration_s: number;
  transcript: string;
}

export interface ReviewVersion {
  id: number;
  session_id: number;
  number: number;
  label: string;
  message: string;
  status: string;
  filename: string;
  size: number;
  duration_s: number;
  audio_format: string;
  created_at: string;
  round_number: number;
  waveform: number[];
  waveform_synthetic: boolean;
  comments: ReviewComment[];
  watermarked: boolean;
  commit_id?: number | null;
}

export interface VersionDiff {
  version_label: string;
  from_label?: string | null;
  path?: string | null;
  format?: string | null;
  has_daw: boolean;
  summary: DiffChange[];
  raw: string;
  truncated: boolean;
}

export interface ReviewRound {
  id: number;
  number: number;
  status: string;
  submitted_at: string | null;
  due_at: string | null;
  note: string;
  request_count: number;
}

export const REQUEST_STATUSES = ["open", "acknowledged", "in_progress", "fixed", "verified", "approved"] as const;
export type RequestStatus = (typeof REQUEST_STATUSES)[number];

export interface ReviewApproval {
  id: number;
  session_id: number;
  version_id: number;
  scope: string;
  approved: boolean;
  note: string;
  approver_name: string;
  role: string;
  created_at: string;
}

export interface SessionMember {
  id: number;
  session_id: number;
  email: string;
  role: string;
  invited_by: string;
  created_at: string;
}

export interface ShareAccessEvent {
  id: number;
  actor: string;
  action: string;
  detail: string;
  created_at: string;
}

export interface ReviewSession {
  id: number;
  project_id: number | null;
  name: string;
  status: string;
  share_token: string;
  created_at: string;
  updated_at: string;
  owner_username: string;
  version_count: number;
  latest_status: string;
  versions?: ReviewVersion[];
  approvals?: ReviewApproval[];
  access_events?: ShareAccessEvent[];
  rounds?: ReviewRound[];
  share_expires_at?: string | null;
  share_permission?: string;
  share_has_password?: boolean;
  share_allowlist?: string;
  round_number?: number;
  feedback_due_at?: string | null;
  feedback_owner?: string;
  included_rounds?: number;
  rounds_open?: boolean;
  deposit_due_cents?: number | null;
  deposit_status?: string;
  extra_round_price_cents?: number | null;
  rounds_paid?: number;
  portfolio_public?: boolean;
  watermark_enabled?: boolean;
  retention_until?: string | null;
  recall_fee_cents?: number | null;
  revision_fee_cents?: number | null;
  change_rounds_granted?: number;
  reminders_enabled?: boolean;
  reminder_categories?: string;
  reminders_client_opt_out?: boolean;
  client_email?: string;
  approval_preset?: string;
  members?: SessionMember[];
  service_type?: string;
  genre?: string;
  goal?: string;
  deadline_at?: string | null;
  review_start_at?: string | null;
  reference_links?: string;
  do_not_change?: string;
  required_deliverables?: string;
}

export interface NotificationOut {
  id: number;
  session_id: number;
  kind: string;
  channel: string;
  recipient: string;
  subject: string;
  body: string;
  cta_url: string;
  cta_label: string;
  status: "queued" | "sent" | "failed" | "dismissed";
  error: string;
  sent_at: string | null;
  created_at: string;
}

export interface ReminderSettings {
  reminders_enabled: boolean;
  reminder_categories: string;
  client_email: string;
  client_opted_out: boolean;
}

export interface SessionRemindersResponse {
  settings: ReminderSettings;
  notifications: NotificationOut[];
}

export interface RemindersEvalResult {
  evaluated: number;
  created: number;
  sent: number;
  failed: number;
  dismissed: number;
}

export const APPROVAL_PRESETS = [
  { id: "solo_client", label: "Solo client", description: "Engineer + client — client approves, no role setup" },
  { id: "artist_team", label: "Artist team", description: "Engineer + artist + feedback owner" },
  { id: "label_workflow", label: "Label workflow", description: "Artist: mix · A&R: master · label admin: release" },
  { id: "post_production", label: "Post-production", description: "Engineer + producer + director" },
] as const;

export const TEAM_ROLES = [
  { id: "artist", label: "Artist" },
  { id: "a_r", label: "A&R" },
  { id: "label_admin", label: "Label admin" },
  { id: "producer", label: "Producer" },
  { id: "director", label: "Director" },
  { id: "feedback_owner", label: "Feedback owner" },
  { id: "viewer", label: "Viewer" },
] as const;

export interface ApprovalPolicy {
  preset: string;
  preset_label: string;
  enforced: boolean;
  policy: Record<string, string[]>;
  roles: string[];
}

export const REMINDER_CATEGORIES = [
  { id: "review", label: "Review & approval" },
  { id: "feedback", label: "Feedback deadlines & idle drafts" },
  { id: "invoice", label: "Invoice due / overdue" },
  { id: "change_order", label: "Change-order quotes" },
  { id: "archive", label: "Archive expiry" },
  { id: "delivery", label: "Delivery link expiry" },
] as const;

export interface PortfolioTrack {
  session_id: number;
  name: string;
  status: string;
  version_count: number;
  has_approved: boolean;
  approved_label: string;
  approved_filename: string;
  approved_version_id: number | null;
  approved_duration_s: number;
  approved_at: string | null;
  delivery_token: string | null;
}

export interface Reputation {
  delivered_count: number;
  approved_count: number;
  session_count: number;
  avg_rounds: number | null;
  on_time_rate: number | null;
  verified: boolean;
  badges: string[];
  bio: string;
  specialty: string;
  location: string;
}

export interface Portfolio {
  username: string;
  track_count: number;
  tracks: PortfolioTrack[];
  reputation: Reputation | null;
}

export interface SearchEngineer {
  username: string;
  session_count: number;
}

export interface SearchSessionHit {
  name: string;
  owner_username: string;
  share_token: string;
  status: string;
  updated_at?: string;
}

export interface SearchResults {
  query: string;
  engineers: SearchEngineer[];
  sessions: SearchSessionHit[];
}

export const APPROVAL_SCOPES = ["mix", "master", "arrangement", "release"] as const;
export type ApprovalScope = (typeof APPROVAL_SCOPES)[number];

export interface Deliverable {
  id: number;
  package_id: number;
  type: string;
  filename: string;
  size: number;
  sha256: string | null;
  format: string;
  sample_rate: number | null;
  bit_depth: number | null;
  channels: number | null;
  integrated_lufs: number | null;
  true_peak: number | null;
  is_required: boolean;
  source_version_id: number | null;
  created_at: string;
}

export interface DeliveryEvent {
  event: string;
  actor: string;
  detail: string;
  created_at: string;
}

export interface ReleasePackage {
  id: number;
  session_id: number;
  approved_version_id: number;
  name: string;
  status: string;
  invoice_status: string;
  amount_due_cents: number | null;
  currency: string;
  immutable_at: string | null;
  manifest_hash: string | null;
  delivery_token: string | null;
  created_at: string;
  locked_by: string;
  template: string;
  plugin_manifest: string;
  session_manifest: Record<string, unknown>;
  consolidate_audio: boolean;
  archive_expires_at: string | null;
  archive_status: string;
  last_verified_opened_at: string | null;
  invoice_due_at?: string | null;
  force_locked_reason: string;
  force_locked_by: string;
  deliverables: Deliverable[];
  events: DeliveryEvent[];
}

export interface ReleaseTemplate {
  id: string;
  name: string;
  description: string;
  deliverable_types: string[];
  note: string;
}

export interface PreflightCheck {
  status: "ok" | "warn" | "block";
  label: string;
  detail: string;
}

export interface PreflightResult {
  passed: boolean;
  blocking: boolean;
  checks: PreflightCheck[];
}

export const CHANGE_ORDER_REASONS = ["mix_revision", "new_stem_request", "format_change", "mastering_recall"] as const;
export const CHANGE_ORDER_DECISIONS = ["courtesy", "paid_round", "new_mastering_pass"] as const;

export interface ChangeOrder {
  id: number;
  session_id: number;
  created_by: string;
  reason: string;
  description: string;
  status: string;
  decision: string | null;
  price_cents: number | null;
  currency: string;
  deadline_at: string | null;
  target_round: number;
  round_granted: boolean;
  quote_version: number;
  quote_expires_at: string | null;
  quoted_at: string | null;
  accepted_at: string | null;
  paid_at: string | null;
  declined_at: string | null;
  created_at: string;
}

export interface DeliveryPage {
  id: number;
  name: string;
  status: string;
  invoice_status: string;
  amount_due_cents: number | null;
  currency: string;
  deposit_due_cents: number | null;
  deposit_status: string;
  locked_by: string;
  immutable_at: string | null;
  manifest_hash: string | null;
  approved_label: string;
  approved_filename: string;
  template: string;
  archive_status: string;
  archive_expires_at: string | null;
  last_verified_opened_at: string | null;
  invoice_due_at?: string | null;
  retention_until: string | null;
  share_token: string;
  deliverables: Deliverable[];
}

export interface CheckoutOut {
  checkout_url: string;
  session_id: string;
  amount_due_cents: number;
  currency: string;
}

export interface UsdcCheckoutOut {
  network: string;
  chain_id: number;
  token_address: string;
  payee_address: string;
  amount_usdc_units: number;
  amount_usdc: number;
  decimals: number;
  purpose: string;
  expires_at: number;
}

export interface UsdcTransfer {
  from: string;
  to: string;
  value: number;
  log_index: number;
}

export interface UsdcVerifyOut {
  ok: boolean;
  handled: boolean;
  already_paid?: boolean;
  transfer?: UsdcTransfer | null;
}

export const DELIVERABLE_TYPES = ["master", "instrumental", "acapella", "clean_edit", "stems", "artwork", "other"] as const;

export interface LedgerEntry {
  id: number;
  event: string;
  actor: string;
  entity_type: string;
  entity_id: number | null;
  payload: Record<string, unknown>;
  occurred_at: string;
  prev_event_hash: string | null;
  event_hash: string;
}

export interface LedgerResponse {
  events: LedgerEntry[];
  head_hash: string | null;
}

export interface LedgerVerify {
  ok: boolean;
  total: number;
  head_hash: string | null;
  problems: Array<{ id: number; event: string; expected: string; stored: string }>;
}

export const REFERENCE_PURPOSES = ["balance", "low_end", "vocal", "width", "arrangement", "overall"] as const;
export const REFERENCE_VISIBILITY = ["engineer_only", "reviewers"] as const;

export interface ReferenceTrack {
  id: number;
  session_id: number;
  title: string;
  artist: string;
  source_type: "external_url" | "private_upload";
  external_url: string;
  purpose: string;
  visibility: string;
  note: string;
  created_by: string;
  created_at: string;
  filename: string;
  size: number;
  audio_format: string;
  duration_s: number;
  integrated_lufs: number | null;
  true_peak_dbtp: number | null;
  sample_rate: number | null;
  channels: number | null;
  analysis_status: string;
  waveform: number[];
  waveform_synthetic: boolean;
}

export interface ReferenceComparison {
  id: number;
  session_id: number;
  version_id: number;
  reference_id: number;
  version_label: string;
  reference_label: string;
  start_ms: number;
  end_ms: number | null;
  mix_gain_db: number;
  ref_gain_db: number;
  short_term_lufs: Record<string, number>;
  level_match: string;
  label: string;
  mix_audio_url: string;
  ref_audio_url: string;
  created_at: string;
}

export interface AudioAnalysis {
  version_id: number | null;
  duration_ms: number;
  sample_rate: number | null;
  channels: number | null;
  integrated_lufs: number | null;
  true_peak_dbtp: number | null;
  analysis_status: string;
  analysed_at: string | null;
}

export interface StemAsset {
  id: number;
  version_id: number;
  logical_name: string;
  display_name: string;
  size: number;
  audio_format: string;
  start_offset_ms: number;
  created_at: string;
}

export const STEM_LOGICAL_NAMES = ["drums", "bass", "vocal", "synths", "other"] as const;

export interface VersionComparison {
  id: number;
  session_id: number;
  base_version_id: number;
  compare_version_id: number;
  base_label: string;
  compare_label: string;
  request_id: number | null;
  start_ms: number;
  end_ms: number | null;
  base_gain_db: number;
  compare_gain_db: number;
  short_term_lufs: Record<string, number>;
  level_match: string;
  label: string;
  mode: string;
  stem_logical_name: string | null;
  created_at: string;
}

export function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
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
