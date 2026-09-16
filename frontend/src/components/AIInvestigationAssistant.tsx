import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { AssistantMessage } from "../types";

interface Props {
  /** Context passed through to the backend so the assistant can ground its
   * answer in real data. At least one of these (or a device id typed
   * directly into a question) is required by the API. */
  alertId?: string;
  customerId?: string;
  deviceId?: string;
  /** Shown as clickable chips before the analyst has asked anything. */
  suggestedQuestions?: string[];
  title?: string;
  /** Compact mode drops the card chrome so this fits inside another card. */
  compact?: boolean;
}

const DEFAULT_SUGGESTIONS = [
  "Why is this customer suspicious?",
  "Show me unusual activity from this customer.",
  "What transactions are connected to this device?",
  "Summarize this investigation.",
];

export default function AIInvestigationAssistant({
  alertId,
  customerId,
  deviceId,
  suggestedQuestions = DEFAULT_SUGGESTIONS,
  title = "AI Investigation Assistant",
  compact = false,
}: Props) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, asking]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || asking) return;

    setError(null);
    const nextMessages: AssistantMessage[] = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    setAsking(true);
    try {
      const { data } = await api.post("/investigation/ask", {
        question: text,
        alert_id: alertId,
        customer_id: customerId,
        device_id: deviceId,
        conversation_history: messages, // history BEFORE this turn, oldest first
      });
      setMessages([...nextMessages, { role: "assistant", content: data.answer }]);
    } catch (err: any) {
      const message =
        err?.response?.data?.error?.message ||
        (err?.response?.status === 400
          ? "I need a customer, alert, or device to investigate — try mentioning one in your question."
          : "Something went wrong asking the assistant. Please try again.");
      setError(message);
      setMessages(nextMessages); // keep the analyst's question visible even though it failed
    } finally {
      setAsking(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    send(input);
  }

  return (
    <div className={compact ? "" : "bg-white rounded-xl shadow-card border border-primary-100/70 p-4 dark:bg-[#141a2e] dark:border-white/10 dark:shadow-none"}>
      {title && (
        <div className="flex items-center gap-2 mb-1">
          <h2 className="font-semibold">{title}</h2>
          <span className="text-[10px] uppercase tracking-wide bg-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded-full dark:bg-indigo-500/20 dark:text-indigo-300">AI</span>
        </div>
      )}
      <p className="text-xs text-slate-500 mb-3 dark:text-slate-400">
        Ask about this {alertId ? "alert" : ""}
        {alertId && customerId ? " or " : ""}
        {customerId ? "customer" : ""}
        {deviceId ? (alertId || customerId ? " or device" : "device") : ""} — answers are grounded only in real platform data.
      </p>

      {messages.length === 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {suggestedQuestions.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => send(q)}
              disabled={asking}
              className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1.5 rounded-full disabled:opacity-50 dark:bg-white/10 dark:hover:bg-white/20 dark:text-slate-200"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {messages.length > 0 && (
        <div ref={scrollRef} className="max-h-80 overflow-y-auto space-y-2 mb-3 pr-1">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <pre
                className={`whitespace-pre-wrap font-sans text-sm rounded-lg px-3 py-2 max-w-[90%] ${
                  m.role === "user"
                    ? "bg-primary-600 text-white"
                    : "bg-slate-50 text-slate-700 border border-slate-100 dark:bg-white/5 dark:text-slate-200 dark:border-white/10"
                }`}
              >
                {m.content}
              </pre>
            </div>
          ))}
          {asking && (
            <div className="flex justify-start">
              <div className="bg-slate-50 border border-slate-100 rounded-lg px-3 py-2 text-sm text-slate-400 dark:bg-white/5 dark:border-white/10 dark:text-slate-500">Thinking…</div>
            </div>
          )}
        </div>
      )}

      {error && <p className="text-xs text-red-600 mb-2 dark:text-red-400">{error}</p>}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          className="flex-1 border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition bg-white dark:bg-white/5 dark:border-white/10 dark:text-slate-100 dark:placeholder:text-slate-500"
          placeholder="Ask the AI assistant a question..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button disabled={asking || !input.trim()} className="bg-primary-600 text-white text-sm px-3 py-1.5 rounded-lg disabled:opacity-50">
          {asking ? "..." : "Ask"}
        </button>
      </form>
    </div>
  );
}
