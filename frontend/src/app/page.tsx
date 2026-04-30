"use client";

import { useState, useRef, useEffect } from "react";

interface DisambiguationCandidate {
  title: string;
  raw_title: string;
  raw_author: string;
  source: string;
}

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
  };
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, streamStatus]);

  const handleSendMessage = (text: string) => {
    if (!text.trim()) return;
    sendMessage(text.trim());
  };

  const sendMessage = async (userMessage: string) => {
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);
    setStreamStatus("Connecting...");

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      if (!res.ok) throw new Error("Failed to communicate with the server");

      const reader = res.body?.getReader();
      const decoder = new TextDecoder("utf-8");

      if (!reader) {
        throw new Error("No reader available");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process SSE lines
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || ""; // Keep the last incomplete part in the buffer

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.replace("data: ", "").trim();
            if (!dataStr) continue;

            try {
              const data = JSON.parse(dataStr);

              if (data.type === "status") {
                setStreamStatus(data.message);
              } else if (data.type === "result") {
                let botContent = "";
                if (data.data.status === "success") {
                  botContent = `Found "${data.data.book_name}"!`;
                } else {
                  botContent = `Sorry, I couldn't find a link. Reason: ${data.data.reason}`;
                }

                setMessages((prev) => [
                  ...prev,
                  { role: "bot", content: botContent, result: data.data },
                ]);
                setLoading(false);
                setStreamStatus("");
              } else if (data.type === "disambiguation") {
                setMessages((prev) => [
                  ...prev,
                  { role: "bot", content: "Found multiple matches. Which one did you mean?", result: data.data },
                ]);
                setLoading(false);
                setStreamStatus("");
              }
            } catch (err) {
              console.error("Failed to parse SSE data:", err, dataStr);
            }
          }
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: "Oops, something went wrong while searching." },
      ]);
      setLoading(false);
      setStreamStatus("");
    }
  };

  const handleDownload = (url: string) => {
    // Navigate to the download proxy endpoint to avoid CORS issues and force download
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
    window.location.href = `${apiUrl}/api/download?url=${encodeURIComponent(url)}`;
  };

  return (
    <div className="flex flex-col h-screen bg-white text-zinc-900 font-sans selection:bg-zinc-200">
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-md border-b border-zinc-100 px-6 py-4 flex items-center justify-center">
        <h1 className="text-lg font-semibold tracking-tight text-zinc-800">Grabbertoullie</h1>
      </header>

      <div className="flex-1 overflow-y-auto px-4 sm:px-6 md:px-8 pb-32 pt-8">
        <div className="max-w-3xl mx-auto space-y-8">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center mt-20 text-center space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <div className="w-16 h-16 bg-zinc-100 rounded-full flex items-center justify-center mb-2">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8 text-zinc-400">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
                </svg>
              </div>
              <h2 className="text-2xl font-semibold text-zinc-800">What book are you looking for?</h2>
              <p className="text-zinc-500 max-w-md">
                Simply type the name of the book you want to find. For example, <span className="text-zinc-800 font-medium bg-zinc-100 px-2 py-0.5 rounded-md">grab The Alchemist pdf</span>.
              </p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"
                } animate-in fade-in slide-in-from-bottom-2 duration-300`}
            >
              <div
                className={`max-w-[85%] sm:max-w-[75%] px-5 py-3.5 text-[15px] leading-relaxed flex flex-col gap-3 ${msg.role === "user"
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
                        onClick={() => handleSendMessage(`grab ${candidate.raw_title} by ${candidate.raw_author}`)}
                        className="text-left bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 text-zinc-800 py-2.5 px-4 rounded-xl transition-all duration-200 text-sm font-medium active:scale-[0.98]"
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
                      <span className="text-xs font-semibold bg-zinc-100 text-zinc-700 px-2 py-1 rounded-md">{msg.result.extension?.toUpperCase()}</span>
                    </div>
                    <button
                      onClick={() => handleDownload(msg.result!.file_url!)}
                      className="w-full bg-zinc-900 hover:bg-zinc-800 text-white py-2.5 px-4 rounded-xl transition-all duration-200 text-sm font-medium flex items-center justify-center gap-2 group active:scale-[0.98]"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 group-hover:-translate-y-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      Download File
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start animate-in fade-in duration-300">
              <div className="bg-white border border-zinc-200 px-5 py-4 rounded-3xl rounded-tl-sm shadow-sm text-zinc-500 flex flex-col gap-2">
                <div className="flex gap-1.5 items-center">
                  <div className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce"></div>
                  <div className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: "0.15s" }}></div>
                  <div className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: "0.3s" }}></div>
                </div>
                {streamStatus && (
                  <p className="text-xs text-zinc-500 italic animate-pulse">{streamStatus}</p>
                )}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-transparent pb-6 pt-10 px-4">
        <div className="max-w-3xl mx-auto relative shadow-lg shadow-black/5 rounded-full">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSendMessage(input)}
            placeholder="Type your request here..."
            aria-label="Search for a book"
            className="w-full bg-white border border-zinc-200 shadow-sm rounded-full pl-6 pr-14 py-4 focus:outline-none focus:border-zinc-400 focus:ring-4 focus:ring-zinc-100 transition-all text-zinc-800 placeholder:text-zinc-400 text-[15px]"
            disabled={loading}
          />
          <button
            onClick={() => handleSendMessage(input)}
            disabled={loading || !input.trim()}
            aria-label="Send request"
            className="absolute right-2 top-2 bottom-2 bg-zinc-900 hover:bg-zinc-800 disabled:bg-zinc-300 text-white rounded-full w-10 flex items-center justify-center transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900 focus-visible:ring-offset-2"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 ml-0.5">
              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
            </svg>
          </button>
        </div>
        <p className="text-center text-[11px] text-zinc-400 mt-3 font-medium">
          Press Enter to send. For best results, specify the format (e.g. pdf, epub).
        </p>
      </div>
    </div>
  );
}