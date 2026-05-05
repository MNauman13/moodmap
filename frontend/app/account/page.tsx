"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { supabase } from "@/lib/supabase";
import Navbar from "@/components/Navbar";

// ── API helpers ────────────────────────────────────────────────────────────

async function getAuthHeader(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session ? `Bearer ${session.access_token}` : null;
}

async function fetchConsent(): Promise<{ consent_given: boolean; consent_given_at: string | null }> {
  const auth = await getAuthHeader();
  if (!auth) throw new Error("Not authenticated");
  const res = await fetch("/api/v1/account/consent", { headers: { Authorization: auth } });
  if (!res.ok) throw new Error("Failed to fetch consent status");
  return res.json();
}

async function postConsent(value: boolean): Promise<void> {
  const auth = await getAuthHeader();
  if (!auth) throw new Error("Not authenticated");
  const res = await fetch("/api/v1/account/consent", {
    method: "POST",
    headers: { Authorization: auth, "Content-Type": "application/json" },
    body: JSON.stringify({ consent_given: value }),
  });
  if (!res.ok) throw new Error("Failed to update consent");
}

async function triggerExport(): Promise<void> {
  const auth = await getAuthHeader();
  if (!auth) throw new Error("Not authenticated");
  const res = await fetch("/api/v1/account/export", { headers: { Authorization: auth } });
  if (!res.ok) throw new Error("Export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "moodmap_export.json";
  a.click();
  URL.revokeObjectURL(url);
}

async function fetchNotifications(): Promise<{ notification_enabled: boolean }> {
  const auth = await getAuthHeader();
  if (!auth) throw new Error("Not authenticated");
  const res = await fetch("/api/v1/account/notifications", { headers: { Authorization: auth } });
  if (!res.ok) throw new Error("Failed to fetch notification preference");
  return res.json();
}

async function postNotifications(value: boolean): Promise<void> {
  const auth = await getAuthHeader();
  if (!auth) throw new Error("Not authenticated");
  const res = await fetch("/api/v1/account/notifications", {
    method: "POST",
    headers: { Authorization: auth, "Content-Type": "application/json" },
    body: JSON.stringify({ notification_enabled: value }),
  });
  if (!res.ok) throw new Error("Failed to update notification preference");
}

async function deleteAccount(): Promise<void> {
  const auth = await getAuthHeader();
  if (!auth) throw new Error("Not authenticated");
  const res = await fetch("/api/v1/account", { method: "DELETE", headers: { Authorization: auth } });
  if (res.status !== 204) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Delete failed: ${res.status}`);
  }
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function AccountPage() {
  const router = useRouter();

  const [consentGiven, setConsentGiven]     = useState<boolean | null>(null);
  const [consentDate, setConsentDate]       = useState<string | null>(null);
  const [consentLoading, setConsentLoading] = useState(true);
  const [consentSaving, setConsentSaving]   = useState(false);
  const [consentMsg, setConsentMsg]         = useState<string | null>(null);

  const [notifEnabled, setNotifEnabled]         = useState<boolean | null>(null);
  const [notifLoading, setNotifLoading]         = useState(true);
  const [notifSaving, setNotifSaving]           = useState(false);
  const [notifMsg, setNotifMsg]                 = useState<string | null>(null);

  const [exportLoading, setExportLoading]   = useState(false);
  const [exportMsg, setExportMsg]           = useState<string | null>(null);

  const [deletePhase, setDeletePhase]       = useState<"idle" | "confirm" | "deleting">("idle");
  const [deleteConfirm, setDeleteConfirm]   = useState("");
  const [deleteError, setDeleteError]       = useState<string | null>(null);

  useEffect(() => {
    fetchConsent()
      .then((d) => { setConsentGiven(d.consent_given); setConsentDate(d.consent_given_at); })
      .catch(() => setConsentGiven(false))
      .finally(() => setConsentLoading(false));
    fetchNotifications()
      .then((d) => setNotifEnabled(d.notification_enabled))
      .catch(() => setNotifEnabled(true))
      .finally(() => setNotifLoading(false));
  }, []);

  async function handleConsentToggle(value: boolean) {
    setConsentSaving(true);
    setConsentMsg(null);
    try {
      await postConsent(value);
      setConsentGiven(value);
      setConsentDate(value ? new Date().toISOString() : null);
      setConsentMsg(value ? "Consent recorded." : "Consent withdrawn. No new journal entries can be submitted until you re-enable this.");
    } catch {
      setConsentMsg("Failed to update consent — please try again.");
    } finally {
      setConsentSaving(false);
    }
  }

  async function handleNotifToggle(value: boolean) {
    setNotifSaving(true);
    setNotifMsg(null);
    try {
      await postNotifications(value);
      setNotifEnabled(value);
      setNotifMsg(value ? "Email notifications enabled." : "Email notifications disabled.");
    } catch {
      setNotifMsg("Failed to update — please try again.");
    } finally {
      setNotifSaving(false);
    }
  }

  async function handleExport() {
    setExportLoading(true);
    setExportMsg(null);
    try {
      await triggerExport();
      setExportMsg("Your data has been downloaded.");
    } catch {
      setExportMsg("Export failed — please try again.");
    } finally {
      setExportLoading(false);
    }
  }

  async function handleDeleteConfirm() {
    if (deleteConfirm !== "DELETE") return;
    setDeletePhase("deleting");
    setDeleteError(null);
    try {
      await deleteAccount();
      await supabase.auth.signOut();
      router.replace("/login");
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Deletion failed. Please try again.");
      setDeletePhase("confirm");
    }
  }

  return (
    <div className="min-h-screen bg-[#0e0d0b] text-[#e8e4dc]" style={{ fontFamily: "var(--font-dm-sans), sans-serif" }}>
      <Navbar />
      <div className="grid px-5" style={{ gridTemplateColumns: "1fr min(680px, 100%) 1fr" }}>
        <div className="col-start-2 py-12 pb-24">

          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <p className="text-[11px] tracking-[0.12em] uppercase text-[#6b6357] font-light mb-2">
              Account Settings
            </p>
            <h1 style={{ fontFamily: "var(--font-lora), serif" }}
              className="text-[clamp(22px,3.5vw,32px)] font-normal text-[#f0ece2] leading-tight mb-10">
              Your data & privacy
            </h1>
          </motion.div>

          {/* ── Privacy notice ── */}
          <Section title="How we use your data" delay={0.05}>
            <div className="text-[13px] text-[#8a8070] font-light leading-relaxed space-y-3">
              <p>
                MoodMap processes your journal entries, voice recordings, and derived mood scores
                to provide you with emotional insights. This data is classified as{" "}
                <span className="text-[#c8bfb0]">special-category personal data</span> under
                GDPR Article 9 because it relates to your mental health.
              </p>
              <p>
                We do not sell your data, share it with third parties for advertising, or use it
                to train AI models without your separate explicit consent. Your audio recordings
                are deleted from our servers immediately after analysis. Text entries and mood
                scores are retained until you delete your account.
              </p>
              <p>
                Your rights under UK/EU GDPR:
              </p>
              <ul className="list-disc list-inside space-y-1 text-[#6b6357]">
                <li><span className="text-[#8a8070]">Art. 15 — Right of access:</span> download everything we hold (see below).</li>
                <li><span className="text-[#8a8070]">Art. 17 — Right to erasure:</span> delete your account and all data permanently.</li>
                <li><span className="text-[#8a8070]">Art. 20 — Portability:</span> your export is machine-readable JSON.</li>
                <li><span className="text-[#8a8070]">Art. 7 — Withdraw consent:</span> you can withdraw at any time below.</li>
              </ul>
            </div>
          </Section>

          {/* ── Consent management ── */}
          <Section title="Processing consent" delay={0.1}>
            {consentLoading ? (
              <div className="h-10 w-full animate-pulse rounded-lg bg-[#141210]" />
            ) : (
              <div className="space-y-4">
                <p className="text-[13px] text-[#8a8070] font-light leading-relaxed">
                  By enabling this, you give MoodMap explicit consent to process your mood and
                  journal data under GDPR Art. 9. You must have consent enabled to submit journal
                  entries. You can withdraw at any time — it will not delete your existing data.
                </p>

                <div className="flex items-center justify-between rounded-xl border border-[#1a1815] bg-[#0c0b09] px-5 py-4">
                  <div>
                    <p className="text-[13px] text-[#c8bfb0]">
                      {consentGiven ? "Consent granted" : "Consent not given"}
                    </p>
                    {consentDate && consentGiven && (
                      <p className="text-[11px] text-[#6b6357] mt-0.5">
                        Recorded {new Date(consentDate).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleConsentToggle(!consentGiven)}
                    disabled={consentSaving}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 ${
                      consentGiven ? "bg-[#c8a96e]" : "bg-[#2a2720]"
                    }`}
                    role="switch"
                    aria-checked={!!consentGiven}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition duration-200 ${
                        consentGiven ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>

                {consentMsg && (
                  <p className="text-[12px] text-[#a09080]">{consentMsg}</p>
                )}
              </div>
            )}
          </Section>

          {/* ── Notifications ── */}
          <Section title="Email notifications" delay={0.13}>
            {notifLoading ? (
              <div className="h-10 w-full animate-pulse rounded-lg bg-[#141210]" />
            ) : (
              <div className="space-y-4">
                <p className="text-[13px] text-[#8a8070] font-light leading-relaxed">
                  When enabled, MoodMap may send you a gentle nudge if your mood patterns
                  suggest you could use some support. You can turn this off at any time.
                </p>

                <div className="flex items-center justify-between rounded-xl border border-[#1a1815] bg-[#0c0b09] px-5 py-4">
                  <div>
                    <p className="text-[13px] text-[#c8bfb0]">
                      {notifEnabled ? "Notifications on" : "Notifications off"}
                    </p>
                    <p className="text-[11px] text-[#6b6357] mt-0.5">
                      Nudge and crisis support emails
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleNotifToggle(!notifEnabled)}
                    disabled={notifSaving || notifEnabled === null}
                    className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 ${
                      notifEnabled ? "bg-[#c8a96e]" : "bg-[#2a2720]"
                    }`}
                    role="switch"
                    aria-checked={!!notifEnabled}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition duration-200 ${
                        notifEnabled ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>

                {notifMsg && (
                  <p className="text-[12px] text-[#a09080]">{notifMsg}</p>
                )}
              </div>
            )}
          </Section>

          {/* ── Data export ── */}
          <Section title="Download your data" delay={0.15}>
            <p className="text-[13px] text-[#8a8070] font-light leading-relaxed mb-4">
              Download a copy of everything MoodMap holds for you — journal entries, mood scores,
              AI insights, and account details — as a JSON file. This satisfies your right of
              access (Art. 15) and data portability (Art. 20).
            </p>
            <button
              type="button"
              onClick={handleExport}
              disabled={exportLoading}
              className="inline-flex items-center gap-2 rounded-lg border border-[#2a2720] bg-[#0c0b09] px-5 py-2.5 text-[13px] text-[#c8bfb0] transition-all hover:border-[#c8a96e] hover:text-[#c8a96e] disabled:opacity-50"
            >
              {exportLoading ? "Preparing export…" : "Download my data"}
            </button>
            {exportMsg && (
              <p className="mt-3 text-[12px] text-[#a09080]">{exportMsg}</p>
            )}
          </Section>

          {/* ── Account deletion ── */}
          <Section title="Delete account" delay={0.2} danger>
            <p className="text-[13px] text-[#8a8070] font-light leading-relaxed mb-4">
              Permanently deletes your account and <span className="text-[#e8a4a4]">all associated data</span> — journal
              entries, mood scores, AI nudges, and audio files. This action is irreversible.
              We recommend downloading your data first.
            </p>

            {deletePhase === "idle" && (
              <button
                type="button"
                onClick={() => setDeletePhase("confirm")}
                className="inline-flex items-center gap-2 rounded-lg border border-[#4a1b1b]/60 bg-[#0c0b09] px-5 py-2.5 text-[13px] text-[#c07070] transition-all hover:border-[#8a2a2a] hover:bg-[#8a2a2a]/10"
              >
                Delete my account
              </button>
            )}

            {(deletePhase === "confirm" || deletePhase === "deleting") && (
              <div className="rounded-xl border border-[#4a1b1b]/60 bg-[#0c0b09] p-5 space-y-4">
                <p className="text-[13px] text-[#e8a4a4]">
                  This will permanently erase your account. Type{" "}
                  <span className="font-mono text-[#c8bfb0]">DELETE</span> to confirm.
                </p>
                <input
                  type="text"
                  value={deleteConfirm}
                  onChange={(e) => setDeleteConfirm(e.target.value)}
                  placeholder="Type DELETE to confirm"
                  disabled={deletePhase === "deleting"}
                  className="w-full rounded-lg border border-[#2a2720] bg-[#141210] p-3 text-[13px] text-[#e8e4dc] placeholder-[#4a4438] focus:border-[#8a2a2a] focus:outline-none disabled:opacity-50"
                />
                {deleteError && (
                  <p className="text-[12px] text-[#e8a4a4]">{deleteError}</p>
                )}
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={handleDeleteConfirm}
                    disabled={deleteConfirm !== "DELETE" || deletePhase === "deleting"}
                    className="rounded-lg bg-[#8a2a2a] px-5 py-2.5 text-[13px] text-[#fce8e8] transition-all hover:bg-[#a03030] disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {deletePhase === "deleting" ? "Deleting…" : "Permanently delete"}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setDeletePhase("idle"); setDeleteConfirm(""); setDeleteError(null); }}
                    disabled={deletePhase === "deleting"}
                    className="rounded-lg border border-[#2a2720] px-5 py-2.5 text-[13px] text-[#6b6357] transition-all hover:text-[#c8bfb0] disabled:opacity-40"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </Section>

        </div>
      </div>
    </div>
  );
}

// ── Section wrapper ────────────────────────────────────────────────────────

function Section({
  title, children, delay = 0, danger = false,
}: {
  title: string;
  children: React.ReactNode;
  delay?: number;
  danger?: boolean;
}) {
  return (
    <motion.div
      className="mb-10"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
    >
      <div className={`w-full h-px mb-6 ${danger ? "bg-[#4a1b1b]/40" : "bg-[#1a1815]"}`} />
      <h2
        className={`text-[11px] tracking-[0.12em] uppercase font-light mb-5 ${danger ? "text-[#8a4a4a]" : "text-[#6b6357]"}`}
      >
        {title}
      </h2>
      {children}
    </motion.div>
  );
}
