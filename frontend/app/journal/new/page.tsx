"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { journalApi, uploadAudioToR2 } from "@/lib/api";
import Navbar from "@/components/Navbar";

// ── Types ──────────────────────────────────────────────────────────────────
type RecordingState = "idle" | "recording" | "recorded" | "uploading";
type SubmitState = "idle" | "submitting" | "success" | "error";

const MOOD_TAGS = [
  { label: "calm", emoji: "🌊" },
  { label: "anxious", emoji: "🌀" },
  { label: "grateful", emoji: "✨" },
  { label: "tired", emoji: "🌙" },
  { label: "hopeful", emoji: "🌱" },
  { label: "overwhelmed", emoji: "⛈️" },
  { label: "content", emoji: "☀️" },
  { label: "lonely", emoji: "🌫️" },
];

const MAX_CHARS = 2000;

// ── Waveform bars component ────────────────────────────────────────────────
function LiveWaveform({ isRecording }: { isRecording: boolean }) {
  const bars = Array.from({ length: 28 });
  return (
    <div className="waveform-container">
      {bars.map((_, i) => (
        <div
          key={i}
          className="waveform-bar"
          style={{
            animationDelay: `${(i * 37) % 400}ms`,
            animationPlayState: isRecording ? "running" : "paused",
          }}
        />
      ))}
    </div>
  );
}

// ── Timer display ──────────────────────────────────────────────────────────
function RecordingTimer({ seconds }: { seconds: number }) {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return (
    <span className="timer-text">
      {m}:{s}
    </span>
  );
}

// ── Main Journal Page ──────────────────────────────────────────────────────
export default function JournalPage() {
  const router = useRouter();

  // Text state
  const [text, setText] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Recording state
  const [recordingState, setRecordingState] = useState<RecordingState>("idle");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioObjectKey, setAudioObjectKey] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Submit state
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [text]);

  // ── Recording logic ───────────────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob);
        stream.getTracks().forEach((t) => t.stop());
      };

      mediaRecorder.start(250); // collect data every 250ms
      setRecordingState("recording");
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((s) => {
          if (s >= 179) {
            // 3 min limit
            stopRecording();
            return 180;
          }
          return s + 1;
        });
      }, 1000);
    } catch (err) {
      console.error("Microphone access denied:", err);
      setErrorMessage("Microphone access denied. Please allow mic access and try again.");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) clearInterval(timerRef.current);
    setRecordingState("recorded");
  }, []);

  const discardRecording = useCallback(() => {
    setAudioBlob(null);
    setAudioObjectKey(null);
    setRecordingState("idle");
    setRecordingSeconds(0);
  }, []);

  // ── Upload audio to R2 ────────────────────────────────────────────────────
  const uploadAudio = useCallback(async (): Promise<string | null> => {
    if (!audioBlob) return null;
    setRecordingState("uploading");

    try {
      const objectKey = await uploadAudioToR2(audioBlob, "webm");
      setAudioObjectKey(objectKey);
      setRecordingState("recorded");
      return objectKey;
    } catch (err) {
      console.error("Audio upload failed:", err);
      setErrorMessage("Audio upload failed. Please try again.");
      setRecordingState("recorded");
      return null;
    }
  }, [audioBlob]);

  // ── Submit entry ──────────────────────────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    if (!text.trim()) return;
    setSubmitState("submitting");
    setErrorMessage("");

    try {
      // Upload audio first if we have a recording
      let audioKey = audioObjectKey;
      if (audioBlob && !audioObjectKey) {
        audioKey = await uploadAudio();
        if (!audioKey) {
          throw new Error("Audio upload failed. Please try again.");
        }
      }

      await journalApi.create({
        text: text.trim(),
        audio_key: audioKey,
        mood_tags: selectedTags,
      });

      setSubmitState("success");
      setTimeout(() => router.push("/dashboard"), 1800);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setSubmitState("error");
    }
  }, [text, audioBlob, audioObjectKey, selectedTags, uploadAudio, router]);

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag].slice(0, 5)
    );
  };

  const charCount = text.length;
  const isOverLimit = charCount > MAX_CHARS;
  const hasContent = text.trim().length > 0 || audioBlob !== null || audioObjectKey !== null;
  const canSubmit = hasContent && !isOverLimit && submitState === "idle";

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400&family=DM+Sans:wght@300;400;500&display=swap');

        body {
          background: #0e0d0b;
          color: #e8e4dc;
          font-family: 'DM Sans', sans-serif;
          min-height: 100vh;
        }

        .page-wrap {
          min-height: 100vh;
          display: grid;
          grid-template-columns: 1fr min(680px, 100%) 1fr;
          padding: 0 1rem;
        }

        .page-content {
          grid-column: 2;
          padding: 3rem 0 6rem;
        }

        /* ── Header ── */
        .page-header {
          margin-bottom: 3rem;
        }
        .date-label {
          font-size: 11px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: #8a8070;
          margin-bottom: 0.6rem;
          font-family: 'DM Sans', sans-serif;
          font-weight: 300;
        }
        .page-title {
          font-family: 'Lora', serif;
          font-size: clamp(28px, 5vw, 42px);
          font-weight: 400;
          color: #f0ece2;
          line-height: 1.15;
        }
        .page-title em {
          color: #c8a96e;
          font-style: italic;
        }
        .page-subtitle {
          margin-top: 0.75rem;
          font-size: 14px;
          color: #6b6357;
          font-weight: 300;
          line-height: 1.6;
        }

        /* ── Divider ── */
        .thin-line {
          width: 40px;
          height: 1px;
          background: #c8a96e;
          margin: 2rem 0;
          opacity: 0.5;
        }

        /* ── Textarea ── */
        .journal-textarea-wrap {
          position: relative;
          margin-bottom: 2rem;
        }
        .journal-textarea {
          width: 100%;
          min-height: 240px;
          background: transparent;
          border: none;
          border-bottom: 1px solid #2a2720;
          color: #e8e4dc;
          font-family: 'Lora', serif;
          font-size: 18px;
          font-weight: 400;
          line-height: 1.8;
          resize: none;
          outline: none;
          padding: 0 0 2rem;
          transition: border-color 0.2s;
          overflow: hidden;
          caret-color: #c8a96e;
        }
        .journal-textarea::placeholder {
          color: #3d3830;
          font-style: italic;
        }
        .journal-textarea:focus {
          border-bottom-color: #c8a96e;
        }
        .char-count {
          position: absolute;
          bottom: 0.6rem;
          right: 0;
          font-size: 11px;
          color: #6b6357;
          font-weight: 300;
          transition: color 0.2s;
        }
        .char-count.over { color: #e24b4a; }

        /* ── Section label ── */
        .section-label {
          font-size: 10px;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: #8a8070;
          font-family: 'DM Sans', sans-serif;
          font-weight: 400;
          margin-bottom: 1rem;
        }

        /* ── Mood tags ── */
        .mood-tags-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 2.5rem;
        }
        .mood-tag {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 6px 14px;
          border-radius: 100px;
          border: 1px solid #2a2720;
          background: transparent;
          color: #6b6357;
          font-family: 'DM Sans', sans-serif;
          font-size: 13px;
          font-weight: 300;
          cursor: pointer;
          transition: all 0.18s ease;
          user-select: none;
        }
        .mood-tag:hover {
          border-color: #6b6357;
          color: #a09080;
        }
        .mood-tag.selected {
          background: #1e1c18;
          border-color: #c8a96e;
          color: #c8a96e;
        }
        .mood-tag .emoji {
          font-size: 14px;
          line-height: 1;
        }

        /* ── Voice recorder ── */
        .recorder-section {
          margin-bottom: 2.5rem;
        }
        .recorder-inner {
          background: #141310;
          border: 1px solid #1e1c18;
          border-radius: 12px;
          padding: 1.5rem;
          transition: border-color 0.2s;
        }
        .recorder-inner.active {
          border-color: #c8a96e;
        }
        .recorder-row {
          display: flex;
          align-items: center;
          gap: 1rem;
        }
        .record-btn {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          transition: transform 0.15s ease, background 0.15s;
        }
        .record-btn.idle {
          background: #1e1c18;
        }
        .record-btn.idle:hover {
          background: #2a2720;
          transform: scale(1.05);
        }
        .record-btn.recording {
          background: #c8a96e;
          animation: pulse-btn 1.4s ease-in-out infinite;
        }
        .record-btn.recorded {
          background: #1e1c18;
        }
        @keyframes pulse-btn {
          0%, 100% { box-shadow: 0 0 0 0 rgba(200, 169, 110, 0.3); }
          50% { box-shadow: 0 0 0 10px rgba(200, 169, 110, 0); }
        }
        .record-icon {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: #c8a96e;
        }
        .stop-icon {
          width: 14px;
          height: 14px;
          border-radius: 3px;
          background: #0e0d0b;
        }
        .recorded-icon {
          width: 0;
          height: 0;
          border-top: 8px solid transparent;
          border-bottom: 8px solid transparent;
          border-left: 14px solid #c8a96e;
          margin-left: 2px;
        }
        .recorder-info {
          flex: 1;
        }
        .recorder-status {
          font-size: 13px;
          color: #a09080;
          font-weight: 300;
          line-height: 1.4;
        }
        .recorder-status strong {
          color: #e8e4dc;
          font-weight: 400;
        }
        .timer-text {
          font-family: 'DM Sans', sans-serif;
          font-size: 13px;
          color: #c8a96e;
          font-weight: 400;
          font-variant-numeric: tabular-nums;
        }
        .discard-btn {
          background: none;
          border: none;
          color: #6b6357;
          font-family: 'DM Sans', sans-serif;
          font-size: 12px;
          cursor: pointer;
          padding: 4px 8px;
          border-radius: 4px;
          transition: color 0.15s;
        }
        .discard-btn:hover { color: #8a8070; }

        /* ── Waveform ── */
        .waveform-container {
          display: flex;
          align-items: center;
          gap: 3px;
          height: 32px;
          margin-top: 1rem;
          padding: 0 2px;
        }
        .waveform-bar {
          width: 3px;
          border-radius: 2px;
          background: #c8a96e;
          opacity: 0.6;
          animation: wave-anim 0.8s ease-in-out infinite alternate;
          height: 8px;
        }
        @keyframes wave-anim {
          from { height: 4px; opacity: 0.3; }
          to { height: 28px; opacity: 0.85; }
        }

        /* ── Submit area ── */
        .submit-area {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          flex-wrap: wrap;
        }
        .submit-left {
          font-size: 13px;
          color: #6b6357;
          font-weight: 300;
        }
        .submit-btn {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          padding: 14px 32px;
          background: #c8a96e;
          color: #0e0d0b;
          font-family: 'DM Sans', sans-serif;
          font-size: 14px;
          font-weight: 500;
          border: none;
          border-radius: 100px;
          cursor: pointer;
          transition: all 0.2s ease;
          letter-spacing: 0.02em;
        }
        .submit-btn:hover:not(:disabled) {
          background: #dbb97e;
          transform: translateY(-1px);
        }
        .submit-btn:disabled {
          opacity: 0.35;
          cursor: not-allowed;
          transform: none;
        }
        .submit-btn .arrow {
          font-size: 16px;
          transition: transform 0.2s;
        }
        .submit-btn:hover:not(:disabled) .arrow {
          transform: translateX(3px);
        }

        /* ── Success overlay ── */
        .success-overlay {
          position: fixed;
          inset: 0;
          background: #0e0d0b;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 1rem;
          z-index: 100;
        }
        .success-check {
          width: 64px;
          height: 64px;
          border-radius: 50%;
          background: #1e1c18;
          border: 1px solid #c8a96e;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 28px;
        }
        .success-text {
          font-family: 'Lora', serif;
          font-size: 22px;
          color: #e8e4dc;
          font-style: italic;
        }
        .success-sub {
          font-size: 13px;
          color: #6b6357;
          font-weight: 300;
        }

        /* ── Error banner ── */
        .error-banner {
          background: #1a0f0f;
          border: 1px solid #4a1b1b;
          border-radius: 8px;
          padding: 0.75rem 1rem;
          font-size: 13px;
          color: #e24b4a;
          margin-bottom: 1.5rem;
          font-weight: 300;
        }

        /* ── Uploading indicator ── */
        .uploading-dot {
          display: inline-block;
          width: 6px;
          height: 6px;
          background: #c8a96e;
          border-radius: 50%;
          animation: blink 0.8s ease-in-out infinite alternate;
        }
        @keyframes blink {
          from { opacity: 0.3; }
          to { opacity: 1; }
        }
      `}</style>

      <Navbar />

      {/* Success overlay */}
      <AnimatePresence>
        {submitState === "success" && (
          <motion.div
            className="success-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
          >
            <motion.div
              className="success-check"
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.15, type: "spring", stiffness: 200 }}
            >
              ✓
            </motion.div>
            <motion.p
              className="success-text"
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.3 }}
            >
              Entry saved.
            </motion.p>
            <motion.p
              className="success-sub"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
            >
              Taking you to your dashboard…
            </motion.p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="page-wrap">
        <div className="page-content">
          {/* Header */}
          <motion.div
            className="page-header"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <p className="date-label">
              {new Date().toLocaleDateString("en-GB", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </p>
            <h1 className="page-title">
              How are you <em>really</em> feeling?
            </h1>
            <p className="page-subtitle">
              Write freely. There are no wrong answers here.
            </p>
          </motion.div>

          <div className="thin-line" />

          {/* Error banner */}
          <AnimatePresence>
            {submitState === "error" && (
              <motion.div
                className="error-banner"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                {errorMessage}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Journal textarea */}
          <motion.div
            className="journal-textarea-wrap"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15, duration: 0.5 }}
          >
            <textarea
              ref={textareaRef}
              className="journal-textarea"
              placeholder="Today I noticed…"
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setSubmitState("idle");
              }}
              rows={8}
              autoFocus
            />
            <span className={`char-count ${isOverLimit ? "over" : ""}`}>
              {charCount} / {MAX_CHARS}
            </span>
          </motion.div>

          {/* Mood tags */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
          >
            <p className="section-label">How would you tag this moment?</p>
            <div className="mood-tags-row">
              {MOOD_TAGS.map((tag) => (
                <button
                  key={tag.label}
                  className={`mood-tag ${selectedTags.includes(tag.label) ? "selected" : ""}`}
                  onClick={() => toggleTag(tag.label)}
                  type="button"
                >
                  <span className="emoji">{tag.emoji}</span>
                  {tag.label}
                </button>
              ))}
            </div>
          </motion.div>

          {/* Voice recorder */}
          <motion.div
            className="recorder-section"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35 }}
          >
            <p className="section-label">Add a voice note (optional)</p>
            <div className={`recorder-inner ${recordingState === "recording" ? "active" : ""}`}>
              <div className="recorder-row">
                {/* Record / Stop button */}
                <button
                  className={`record-btn ${recordingState}`}
                  onClick={
                    recordingState === "idle"
                      ? startRecording
                      : recordingState === "recording"
                      ? stopRecording
                      : undefined
                  }
                  type="button"
                  aria-label={
                    recordingState === "idle"
                      ? "Start recording"
                      : recordingState === "recording"
                      ? "Stop recording"
                      : "Recording saved"
                  }
                >
                  {recordingState === "idle" && <div className="record-icon" />}
                  {recordingState === "recording" && <div className="stop-icon" />}
                  {(recordingState === "recorded" || recordingState === "uploading") && (
                    <div className="recorded-icon" />
                  )}
                </button>

                {/* Status text */}
                <div className="recorder-info">
                  {recordingState === "idle" && (
                    <p className="recorder-status">
                      Tap to record up to <strong>3 minutes</strong> of voice
                    </p>
                  )}
                  {recordingState === "recording" && (
                    <p className="recorder-status">
                      Recording… <RecordingTimer seconds={recordingSeconds} />
                    </p>
                  )}
                  {recordingState === "recorded" && (
                    <p className="recorder-status">
                      <strong>Voice note ready</strong> — {Math.floor(recordingSeconds / 60)}m {recordingSeconds % 60}s recorded
                    </p>
                  )}
                  {recordingState === "uploading" && (
                    <p className="recorder-status">
                      Uploading <span className="uploading-dot" />
                    </p>
                  )}
                </div>

                {/* Discard button */}
                {(recordingState === "recorded") && (
                  <button className="discard-btn" onClick={discardRecording} type="button">
                    Remove
                  </button>
                )}
              </div>

              {/* Live waveform */}
              {recordingState === "recording" && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <LiveWaveform isRecording={true} />
                </motion.div>
              )}
            </div>
          </motion.div>

          {/* Submit */}
          <motion.div
            className="submit-area"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.45 }}
          >
            <p className="submit-left">
              {selectedTags.length > 0
                ? `Tagged: ${selectedTags.join(", ")}`
                : "Untagged entry"}
            </p>
            <button
              className="submit-btn"
              onClick={handleSubmit}
              disabled={!canSubmit}
              type="button"
            >
              {submitState === "submitting" ? "Saving…" : "Save entry"}
              {submitState !== "submitting" && <span className="arrow">→</span>}
            </button>
          </motion.div>
        </div>
      </div>
    </>
  );
}
