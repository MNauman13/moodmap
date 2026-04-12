/**
 * useAnalysisStatus — SWR polling hook
 *
 * Polls GET /api/v1/journal/:id/analysis-status every 2s until
 * the status is 'completed' or 'failed', then stops polling.
 *
 * Usage:
 *   const { status, isComplete } = useAnalysisStatus(entryId);
 */
import useSWR from "swr";

type AnalysisStatus = "pending" | "queued" | "processing" | "completed" | "failed";

interface StatusResponse {
    entry_id: string;
    status: AnalysisStatus;
}

const TERMINAL_STATES: AnalysisStatus[] = ["completed", "failed"];

const fetcher = (url: string) =>
    fetch(url).then((r) => {
        if (!r.ok) throw new Error("Failed to fetch status");
        return r.json() as Promise<StatusResponse>;
    });

export function useAnalysisStatus(entryId: string | null) {
    const { data, error, isLoading } = useSWR<StatusResponse>(
        entryId ? `/api/v1/journal/${entryId}/analysis-status` : null,
        fetcher,
        {
            refreshInterval: (data) => {
            // Stop polling once we hit a terminal state
            if (data && TERMINAL_STATES.includes(data.status)) return 0;
            return 2000; // poll every 2s while processing
            },
            revalidateOnFocus: false,
        }
    );

    const status = data?.status ?? null;
    const isComplete = status === "completed";
    const isFailed = status === "failed";
    const isProcessing = status === "processing" || status === "queued";

    return { status, isComplete, isFailed, isProcessing, isLoading, error };
}