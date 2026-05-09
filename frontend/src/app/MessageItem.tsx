import React, { memo } from "react";
import { DisambiguationCandidate } from "./page";

interface ChatMessage {
  role: "user" | "bot";
  content: string;
  result?: {
    status: string;
    book_name?: string;
    file_url?: string;
    extension?: string;
    reason?: string;
    candidates?: DisambiguationCandidate[];
    format?: string;
    source?: string;
  };
}

interface MessageItemProps {
  msg: ChatMessage;
  onSendMessage: (text: string) => void;
  onDownload: (url: string, source?: string) => void;
}

const MessageItem: React.FC<MessageItemProps> = ({ msg, onSendMessage, onDownload }) => {
  return (
    <div
      className={`flex ${
        msg.role === "user" ? "justify-end" : "justify-start"
      } animate-in fade-in slide-in-from-bottom-2 duration-300`}
    >
      <div
        className={`max-w-[85%] sm:max-w-[75%] px-5 py-3.5 text-[15px] leading-relaxed flex flex-col gap-3 ${
          msg.role === "user"
            ? "bg-zinc-900 text-white rounded-3xl rounded-tr-sm"
            : "bg-white border border-zinc-200 text-zinc-800 rounded-3xl rounded-tl-sm shadow-sm"
        }`}
      >
        <p className="whitespace-pre-wrap">{msg.content}</p>

        {msg.result && msg.result.status === "disambiguation_required" && msg.result.candidates && (
          <div className="flex flex-col gap-2 mt-2">
            {msg.result.candidates.map((candidate, i) => (
              <button
                key={i}
                onClick={() => {
                  const formatSuffix = msg.result?.format && msg.result.format !== "any" ? ` ${msg.result.format}` : "";
                  onSendMessage(`grab ${candidate.raw_title} by ${candidate.raw_author}${formatSuffix} [exact]`);
                }}
                className="text-left bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 text-zinc-800 py-2.5 px-4 rounded-xl transition-all duration-200 text-sm font-medium active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 focus-visible:ring-offset-2"
              >
                {candidate.title}
                {candidate.source && (
                  <span className="block text-xs font-normal text-zinc-500 mt-0.5">Source: {candidate.source}</span>
                )}
              </button>
            ))}
          </div>
        )}

        {msg.result && msg.result.status === "success" && msg.result.file_url && (
          <div className="mt-2 pt-4 border-t border-zinc-100/20">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">Format</span>
              <span className="text-xs font-semibold bg-zinc-100 text-zinc-700 px-2 py-1 rounded-md">
                {msg.result.extension?.toUpperCase()}
              </span>
            </div>
            <button
              onClick={() => onDownload(msg.result!.file_url!, msg.result!.source)}
              className="w-full bg-zinc-900 hover:bg-zinc-800 text-white py-2.5 px-4 rounded-xl transition-all duration-200 text-sm font-medium flex items-center justify-center gap-2 group active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 focus-visible:ring-offset-2"
            >
              <svg
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4 group-hover:-translate-y-0.5 transition-transform"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download File
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default memo(MessageItem);
