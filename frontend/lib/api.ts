/**
 * api.ts — typed fetch helpers for MoodMap backend
 *
 * How auth works in this project:
 * - The Next.js route handlers (route.ts) forward the raw Authorization header
 *   directly to FastAPI — they do NOT use Supabase server-side session.
 * - So apiFetch reads the token from supabase.auth.getSession() client-side
 *   and passes it as the Authorization header on every request.
 * - The route handlers then proxy it straight to FastAPI unchanged.
 */
import { supabase } from "@/lib/supabase";

// ── Types — mirror Python Pydantic models exactly ──────────────

export type AnalysisStatus =
  | "pending" | "queued" | "processing"
  | "completed" | "failed"
  | "COMPLETED" | "FAILED";   // uppercase variants kept for backwards-compat with old DB rows

export interface MoodScores {
  text_joy: number | null;
  text_sadness: number | null;
  text_anger: number | null;
  text_fear: number | null;
  text_disgust: number | null;
  text_surprise: number | null;
  text_neutral: number | null;
  voice_valence: number | null;
  voice_arousal: number | null;
  voice_energy: number | null;
  fused_score: number | null;
  dominant_emotion: string | null;
  confidence: number | null;
}

export interface JournalEntryResponse {
  id: string;
  user_id: string;
  text: string;
  audio_key: string | null;
  audio_url: string | null;
  word_count: number;
  mood_tags: string[];
  status: AnalysisStatus;
  mood_scores: MoodScores | null;
  created_at: string;  // ISO datetime string from Python
}

export interface JournalEntryCreatedResponse {
  entry_id: string;
  status: AnalysisStatus;
  task_id: string;
  message: string;
}

export interface JournalListResponse {
  entries: JournalEntryResponse[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface JournalEntryCreate {
  text: string;
  audio_key?: string | null;
  mood_tags?: string[];
}

export interface PresignedUrlResponse {
  upload_url: string;
  fields: Record<string, string>; // must be included in the multipart POST body
  object_key: string;
  expires_in: number;
  max_bytes: number;
}

/**
 * TrendDataPoint and EmotionDataPoint mirror the Pydantic schemas
 * defined inline in insights.py.
 *
 * TrendDataPoint.date comes from score.time.strftime("%Y-%m-%d")
 * where score.time = entry.created_at (set in analysis.py).
 *
 * EmotionDataPoint.name is capitalized via .capitalize() in insights.py,
 * so "joy" → "Joy". The EMOTION_COLORS map in the components uses
 * capitalized keys to match.
 */
export interface TrendDataPoint {
  date: string;   // "YYYY-MM-DD"
  score: number;  // fused_score, range [-1, 1]
}

export interface EmotionDataPoint {
  name: string;   // capitalized: "Joy", "Sadness", etc.
  value: number;  // count of occurrences in the 30-day window
}

export interface InsightsResponse {
  trend_data: TrendDataPoint[];
  emotion_breakdown: EmotionDataPoint[];
  calendar_data: TrendDataPoint[];  // same data as trend_data, separate field for heatmap
}

export interface AnalysisStatusResponse {
  entry_id: string;
  status: AnalysisStatus;
}

// ── Base fetch ─────────────────────────────────────────────────

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  // Get the Supabase JWT client-side — the route handlers forward it as-is
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error("Not authenticated");

  const res = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${session.access_token}`,
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Request failed: ${res.status}`);
  }

  // 204 No Content
  if (res.status === 204) return null as T;

  return res.json() as Promise<T>;
}

// ── Journal API ────────────────────────────────────────────────

export const journalApi = {
  create: (body: JournalEntryCreate) =>
    apiFetch<JournalEntryCreatedResponse>("/journal", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  list: (page = 1, pageSize = 10) =>
    apiFetch<JournalListResponse>(`/journal?page=${page}&page_size=${pageSize}`),

  get: (id: string) =>
    apiFetch<JournalEntryResponse>(`/journal/${id}`),

  delete: (id: string) =>
    apiFetch<null>(`/journal/${id}`, { method: "DELETE" }),

  getPresignedUrl: (fileExtension = "webm") =>
    apiFetch<PresignedUrlResponse>("/journal/presigned-url", {
      method: "POST",
      body: JSON.stringify({ file_extension: fileExtension }),
    }),

  getAnalysisStatus: (id: string) =>
    apiFetch<AnalysisStatusResponse>(`/journal/${id}/analysis-status`),
};

// ── Insights API ───────────────────────────────────────────────

export const insightsApi = {
  /**
   * Fetches from GET /api/v1/insights
   * Returns trend_data + emotion_breakdown + calendar_data for the last 30 days.
   * Most pages should prefer dashboardApi.summary() — it returns the same
   * insights plus recent entries in a single round-trip.
   */
  get: () => apiFetch<InsightsResponse>("/insights"),
};

// ── Dashboard API ──────────────────────────────────────────────

/**
 * Mirrors backend.routers.dashboard.DashboardSummaryResponse.
 * Replaces the old two-call pattern (insightsApi.get + journalApi.list)
 * with a single backend round-trip.
 */
export interface DashboardSummaryResponse {
  insights: InsightsResponse;
  recent_entries: JournalEntryResponse[];
}

export const dashboardApi = {
  summary: () => apiFetch<DashboardSummaryResponse>("/dashboard/summary"),
};

// ── Audio upload ───────────────────────────────────────────────

/**
 * Uploads an audio Blob directly to Cloudflare R2 via presigned URL.
 * The audio never passes through our server.
 * Returns the object_key to include in the journal entry POST body.
 */
export async function uploadAudioToR2(audioBlob: Blob, fileExtension = "webm"): Promise<string> {
  const { upload_url, fields, object_key, max_bytes } = await journalApi.getPresignedUrl(fileExtension);

  if (audioBlob.size > max_bytes) {
    throw new Error(`Audio file is too large (max ${Math.round(max_bytes / 1024 / 1024)} MB).`);
  }

  // R2 presigned POST requires a multipart form — all policy fields must be included
  const form = new FormData();
  Object.entries(fields).forEach(([k, v]) => form.append(k, v));
  form.append("file", audioBlob, `recording.${fileExtension}`);

  const uploadRes = await fetch(upload_url, { method: "POST", body: form });

  if (!uploadRes.ok) throw new Error(`R2 upload failed: ${uploadRes.status}`);
  return object_key;
}

// ── Nudges API Types ──────────────────────────────────────────

/**
 * Mirrors the dict shape returned by GET /api/v1/nudges in nudges.py.
 * Note: backend field is `sent_at` (matching the DB column), not `created_at`.
 */
export interface Nudge {
  id: string;
  nudge_type: string;
  content: string;
  rating: number | null; // 1 helpful, -1 unhelpful, null unrated
  sent_at: string | null;
}

export interface NudgeListResponse {
  nudges: Nudge[];
  page: number;
  page_size: number;
}

// ── Nudges API Helpers ────────────────────────────────────────

export const nudgesApi = {
  list: (page = 1, pageSize = 20) =>
    apiFetch<NudgeListResponse>(`/nudges?page=${page}&page_size=${pageSize}`),

  rate: (id: string, rating: number) =>
    apiFetch<{ message: string; new_weights: Record<string, number> }>(
      `/nudges/${id}/rate`,
      { method: "POST", body: JSON.stringify({ rating }) },
    ),
};