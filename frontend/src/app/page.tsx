"use client";

import { useState } from "react";

interface ChatMessage {
  role: "user" | "bot";
  content: string;
  result?: {
    status: string;
    book_name?: string;
    file_url?: string;
    extension?: string;
    reason?: string;
  };
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      if (!res.ok) throw new Error("Failed to communicate with the server");

      const data = await res.json();

      let botContent = "";
      if (data.status === "success") {
        botContent = `Found "${data.book_name}"!`;
      } else {
        botContent = `Sorry, I couldn't find a link. Reason: ${data.reason}`;
      }

      setMessages((prev) => [
        ...prev,
        { role: "bot", content: botContent, result: data },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "bot", content: "Oops, something went wrong while searching." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (url: string) => {
    // Navigate to the download proxy endpoint to avoid CORS issues and force download
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.location.href = `${apiUrl}/api/download?url=${encodeURIComponent(url)}`;
  };

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto bg-gray-50 border-x border-gray-200">
      <header className="bg-[#075e54] text-white p-4 shadow-md z-10">
        <h1 className="text-xl font-bold">WhatsApp Book Bot (Web Version)</h1>
        <p className="text-sm opacity-80">Command example: "grab The Alchemist pdf"</p>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#e5ddd5] pb-24">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-10 p-4 bg-white/50 rounded-lg max-w-sm mx-auto">
            Welcome! I can help you find direct download links for books. Type a command to get started.
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[80%] p-3 rounded-lg shadow-sm ${
                msg.role === "user"
                  ? "bg-[#dcf8c6] rounded-tr-none text-gray-800"
                  : "bg-white rounded-tl-none text-gray-800"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>

              {msg.result && msg.result.status === "success" && msg.result.file_url && (
                <div className="mt-3 pt-3 border-t border-gray-200">
                  <p className="text-xs text-gray-500 mb-2">Format: {msg.result.extension?.toUpperCase()}</p>
                  <button
                    onClick={() => handleDownload(msg.result!.file_url!)}
                    className="w-full bg-[#128c7e] hover:bg-[#075e54] text-white py-2 px-4 rounded transition-colors text-sm font-semibold flex items-center justify-center gap-2"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
          <div className="flex justify-start">
            <div className="bg-white p-3 rounded-lg rounded-tl-none shadow-sm text-gray-500 text-sm flex gap-1 items-center">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }}></div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white p-3 border-t border-gray-200 fixed bottom-0 max-w-2xl w-full flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="e.g. grab The Alchemist pdf"
          className="flex-1 border border-gray-300 rounded-full px-4 py-2 focus:outline-none focus:border-[#128c7e] text-black"
          disabled={loading}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          className="bg-[#128c7e] hover:bg-[#075e54] text-white rounded-full w-10 h-10 flex items-center justify-center disabled:opacity-50 transition-colors shrink-0"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 ml-1">
            <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
