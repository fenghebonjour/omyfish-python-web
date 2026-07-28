import { getRefreshToken, getToken, setTokens } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function checkOk(res: Response) {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function register(email: string, password: string) {
  const res = await fetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  await checkOk(res);
  return res.json() as Promise<{ userId: string; email: string }>;
}

export interface AuthResult {
  token: string;
  refreshToken: string;
  userId: string;
  email: string;
  role: string;
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  await checkOk(res);
  return res.json() as Promise<AuthResult>;
}

/** Rotates the stored refresh token into a fresh session; false when that fails. */
export async function refreshSession(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as AuthResult;
    setTokens(data.token, data.refreshToken);
    return true;
  } catch {
    return false;
  }
}

// ── Species identification ────────────────────────────────────────────────────

export interface PredictionResult {
  speciesName: string;
  scientificName: string;
  confidence: number;
  rank: number;
  conservationStatus?: string;
  habitat?: string;
  diet?: string;
  maxSizeCm?: number;
  description?: string;
  funFact?: string;
}

export interface IdentificationResponse {
  predictions: PredictionResult[];
  uncertain: boolean;
  imageKey: string;
  isFish?: boolean;
}

export async function identifyFish(image: File, topK = 5): Promise<IdentificationResponse> {
  const form = new FormData();
  form.append("image", image);
  form.append("topK", String(topK));
  const res = await fetch(`${API_URL}/api/v1/species/identify`, { method: "POST", body: form });
  await checkOk(res);
  return res.json();
}

// ── Bite score ────────────────────────────────────────────────────────────────

export interface BiteHourlyScore {
  timestamp: string;
  score: number;
  breakdown: Record<string, number>;
  weightedContribution: Record<string, number>;
  timeOfDayMultiplier: number;
  safetyFlag?: string | null;
}

export interface TimeWindow {
  start: string;
  end: string;
}

export interface SunTimes {
  date: string; // ISO date
  sunrise: string;
  sunset: string;
}

export interface CurrentConditions {
  time: string;
  precipitationMm: number;
  isStorm: boolean;
  isHeavyPrecip: boolean;
}

export interface BiteForecast {
  species: string;
  lat: number;
  lon: number;
  hourly: BiteHourlyScore[];
  bestWindows: BiteHourlyScore[];
  majorWindows: TimeWindow[]; // per day: windows around the top-2 aggregate-score peaks
  minorWindows: TimeWindow[]; // per day: windows around the next-2 peaks
  sunTimes: SunTimes[]; // per-day sunrise/sunset (drives the dawn/dusk score boost)
  current: CurrentConditions | null; // live nowcast for "right now" alerts
}

// species accepts a profile key or any common/scientific name from a
// confirmed fish ID — the backend resolves it (general fallback).
export async function getBiteScoreToday(
  lat: number,
  lon: number,
  species = "general",
): Promise<BiteForecast> {
  const res = await fetch(
    `${API_URL}/api/v1/species/bite-score/today?lat=${lat}&lon=${lon}&species=${encodeURIComponent(species)}`,
  );
  await checkOk(res);
  return res.json();
}

export async function getBiteScoreForecast(
  lat: number,
  lon: number,
  species = "general",
  hours = 336,
): Promise<BiteForecast> {
  const res = await fetch(
    `${API_URL}/api/v1/species/bite-score/forecast?lat=${lat}&lon=${lon}&species=${encodeURIComponent(species)}&hours=${hours}`,
  );
  await checkOk(res);
  return res.json();
}

// ── Observations ──────────────────────────────────────────────────────────────

export interface Observation {
  id: string;
  userId: string;
  speciesName: string;
  scientificName: string;
  topConfidence: number;
  imageStorageKey: string;
  latitude: number | null;
  longitude: number | null;
  notes: string | null;
  observedAt: string;
  createdAt: string;
}

export async function getObservations(): Promise<Observation[]> {
  const res = await fetch(`${API_URL}/api/v1/observations`, {
    headers: authHeaders(),
  });
  await checkOk(res);
  return res.json();
}

export async function createObservation(body: {
  speciesName: string;
  scientificName: string;
  topConfidence: number;
  imageStorageKey: string;
  latitude?: number | null;
  longitude?: number | null;
  notes?: string | null;
}): Promise<Observation> {
  const res = await fetch(`${API_URL}/api/v1/observations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  await checkOk(res);
  return res.json();
}

export async function deleteObservation(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/observations/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
}

export async function getObservationsGeoJson(): Promise<object> {
  const res = await fetch(`${API_URL}/api/v1/observations/geojson`);
  await checkOk(res);
  return res.json();
}

// ── Species catalog ───────────────────────────────────────────────────────────

export interface SpeciesInfo {
  scientificName: string;
  commonName: string;
  family: string;
  conservationStatus: string;
  habitat: string;
  geographicRange: string;
  description: string;
  northAmericanFreshwater: boolean;
}

export async function getSpecies(northAmericanFreshwater?: boolean): Promise<SpeciesInfo[]> {
  const params =
    northAmericanFreshwater !== undefined ? `?northAmericanFreshwater=${northAmericanFreshwater}` : "";
  const res = await fetch(`${API_URL}/api/v1/species${params}`);
  await checkOk(res);
  return res.json();
}

// ── Notifications ─────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  userId: string;
  type: string;
  title: string;
  body: string | null;
  read: boolean;
  createdAt: string;
}

export async function getNotifications(): Promise<Notification[]> {
  const res = await fetch(`${API_URL}/api/v1/notifications`, {
    headers: authHeaders(),
  });
  await checkOk(res);
  return res.json();
}

export async function markNotificationRead(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/notifications/${id}/read`, {
    method: "PUT",
    headers: authHeaders(),
  });
  await checkOk(res);
}

// ── Billing ───────────────────────────────────────────────────────────────────

export interface Subscription {
  status: string; // trialing | active | canceled | expired
  plan: string | null;
  trialEnd: string | null;
  currentPeriodEnd: string | null;
}

export async function getMySubscription(): Promise<Subscription> {
  const res = await fetch(`${API_URL}/api/billing/me`, { headers: authHeaders() });
  await checkOk(res);
  return res.json();
}

export async function createCheckout(plan: "monthly" | "yearly"): Promise<string> {
  const res = await fetch(`${API_URL}/api/billing/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ plan }),
  });
  await checkOk(res);
  return (await res.json()).checkoutUrl as string;
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export interface AdminStats {
  trialing: number;
  active: number;
  canceled: number;
  expired: number;
  activeMonthly: number;
  activeYearly: number;
  mrrCad: number;
}

export interface AdminSubscriptionRow {
  userId: string;
  email: string;
  status: string;
  plan: string | null;
  trialEnd: string | null;
  currentPeriodEnd: string | null;
}

export async function getAdminStats(): Promise<AdminStats> {
  const res = await fetch(`${API_URL}/api/admin/stats`, { headers: authHeaders() });
  await checkOk(res);
  return res.json();
}

export async function getAdminSubscriptions(): Promise<AdminSubscriptionRow[]> {
  const res = await fetch(`${API_URL}/api/admin/subscriptions`, { headers: authHeaders() });
  await checkOk(res);
  return res.json();
}

async function adminPost(path: string, body?: object): Promise<AdminSubscriptionRow> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body ?? {}),
  });
  await checkOk(res);
  return res.json();
}

export const adminGrant = (userId: string, days = 365, plan = "yearly") =>
  adminPost(`/api/admin/subscriptions/${userId}/grant`, { days, plan });

export const adminRevoke = (userId: string) =>
  adminPost(`/api/admin/subscriptions/${userId}/revoke`);

export const adminExtendTrial = (userId: string, days = 7) =>
  adminPost(`/api/admin/subscriptions/${userId}/extend-trial`, { days });
