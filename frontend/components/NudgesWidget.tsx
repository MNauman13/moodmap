'use client'

import { useEffect, useState } from "react"
import Link from "next/link"
import { nudgesApi, type Nudge } from "@/lib/api"

export default function NudgesWidget() {
    const [unratedNudges, setUnratedNudges] = useState<Nudge[]>([])
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        const fetchNudges = async () => {
            try {
                const data = await nudgesApi.list()
                // Only keep the ones the user hasn't rated yet
                const unrated = data.filter(n => n.rating === null)
                setUnratedNudges(unrated)
            } catch (error) {
                console.error("Failed to fetch nudges:", error)
            } finally {
                setIsLoading(false)
            }
        }
        fetchNudges()
    }, [])

    const handleRate = async (nudgeId: string, rating: number) => {
        // Optimistically remove the rated nudge from the local queue
        setUnratedNudges(prev => prev.filter(n => n.id !== nudgeId))
        
        try {
            await nudgesApi.rate(nudgeId, rating)
        } catch (error) {
            console.error("Failed to rate nudge:", error)
        }
    }

    if (isLoading) {
        return (
            <div className="h-32 w-full animate-pulse rounded-xl bg-[#141210] border border-[#1a1815]"></div>
        )
    }

    const currentNudge = unratedNudges[0]
    const remainingCount = unratedNudges.length

    if (!currentNudge) {
        return (
            <div className="flex items-center justify-between rounded-xl border border-[#1a1815] bg-[#0c0b09] p-5">
                <div>
                    <h3 className="font-['Lora'] text-[16px] text-[#c8bfb0]">Insights caught up</h3>
                    <p className="text-[12px] font-light text-[#6b6357] mt-1">Keep journaling to generate new AI interventions.</p>
                </div>
                <Link href="/nudges" className="text-[12px] text-[#c8a96e] hover:text-[#e8e4dc] transition-colors">
                    View History →
                </Link>
            </div>
        )
    }

    return (
        <div className="relative overflow-hidden rounded-xl border border-[#c8a96e]/30 bg-[#0c0b09] p-6 shadow-[0_0_15px_rgba(200,169,110,0.05)] transition-all">
            {/* Ambient glow effect in the corner */}
            <div className="absolute -right-20 -top-20 h-40 w-40 rounded-full bg-[#c8a96e] opacity-5 blur-[50px]"></div>

            <div className="relative z-10 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2">
                            <span className="relative flex h-2 w-2">
                              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#c8a96e] opacity-75"></span>
                              <span className="relative inline-flex h-2 w-2 rounded-full bg-[#c8a96e]"></span>
                            </span>
                            <span className="text-[12px] font-medium uppercase tracking-wider text-[#c8a96e]">
                                New Insight
                            </span>
                        </div>
                        {remainingCount > 1 && (
                            <span className="rounded-md bg-[#141210] px-2 py-0.5 text-[10px] text-[#6b6357]">
                                1 of {remainingCount}
                            </span>
                        )}
                    </div>
                    
                    <Link href="/nudges" className="text-[11px] text-[#6b6357] hover:text-[#c8a96e] transition-colors">
                        View all
                    </Link>
                </div>

                <p className="font-['Lora'] text-[15px] leading-relaxed text-[#e8e4dc]">
                    {currentNudge.content}
                </p>

                <div className="mt-2 flex items-center justify-between border-t border-[#1a1815] pt-4">
                    <span className="text-[12px] text-[#6b6357]">Did this resonate with you?</span>
                    <div className="flex gap-2">
                        <button 
                            onClick={() => handleRate(currentNudge.id, 1)}
                            className="flex h-8 w-8 items-center justify-center rounded-full border border-[#2a2720] text-[14px] transition-all hover:border-[#c8a96e] hover:bg-[#c8a96e]/10 active:scale-95"
                            title="This was helpful"
                        >
                            👍
                        </button>
                        <button 
                            onClick={() => handleRate(currentNudge.id, -1)}
                            className="flex h-8 w-8 items-center justify-center rounded-full border border-[#2a2720] text-[14px] transition-all hover:border-[#8a2a2a] hover:bg-[#8a2a2a]/10 active:scale-95"
                            title="Not helpful"
                        >
                            👎
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}