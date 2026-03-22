"use client";

import { ChatStatus } from "@/lib/types";

interface ProgressStepsProps {
  status: ChatStatus;
}

const stages = [
  { key: "rewriting", label: "Analyzing", icon: "🔍" },
  { key: "searching", label: "Searching", icon: "📚" },
  { key: "ranking", label: "Finding best matches", icon: "🎯" },
];

export function ProgressSteps({ status }: ProgressStepsProps) {
  if (status.stage === "idle" || status.stage === "done") return null;

  const currentIndex = stages.findIndex((s) => s.key === status.stage);

  return (
    <div className="flex justify-start mb-4">
      <div className="bg-white rounded-2xl rounded-bl-md shadow-sm px-4 py-3 max-w-md">
        <div className="flex items-center gap-3">
          {/* Spinner */}
          <div className="w-5 h-5 border-2 border-[var(--coral)] border-t-transparent rounded-full spinner" />

          {/* Status message */}
          <div className="text-sm text-gray-600">
            {status.message || "Processing..."}
          </div>
        </div>

        {/* Progress dots */}
        <div className="flex items-center gap-2 mt-3">
          {stages.map((stage, index) => (
            <div key={stage.key} className="flex items-center">
              <div
                className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs
                  ${
                    index < currentIndex
                      ? "bg-green-100 text-green-700"
                      : index === currentIndex
                      ? "bg-[var(--coral)]/20 text-[var(--coral)]"
                      : "bg-gray-100 text-gray-400"
                  }`}
              >
                <span>{stage.icon}</span>
                <span className="hidden sm:inline">{stage.label}</span>
              </div>
              {index < stages.length - 1 && (
                <div
                  className={`w-4 h-0.5 mx-1 ${
                    index < currentIndex ? "bg-green-300" : "bg-gray-200"
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
