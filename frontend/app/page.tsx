'use client';

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type Message = {
  role: 'user' | 'assistant';
  content: string;
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-4 py-3">
      <div className="typing-dot w-2 h-2 rounded-full bg-emerald-400" />
      <div className="typing-dot w-2 h-2 rounded-full bg-emerald-400" />
      <div className="typing-dot w-2 h-2 rounded-full bg-emerald-400" />
    </div>
  );
}

function SkeletonLoader() {
  return (
    <div className="space-y-3 p-4">
      <div className="skeleton h-4 w-3/4" />
      <div className="skeleton h-4 w-1/2" />
      <div className="skeleton h-20 w-full" />
      <div className="skeleton h-4 w-2/3" />
    </div>
  );
}

function ThemeToggle({ isDark, onToggle }: { isDark: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className="p-2 rounded-lg border border-[var(--card-border)] hover:bg-[var(--input-bg)] transition-colors"
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
      )}
    </button>
  );
}
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isDark, setIsDark] = useState(true);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const threadIdRef = useRef('');

  function getThreadId() {
    if (!threadIdRef.current) {
      let id = localStorage.getItem('thread_id');
      if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem('thread_id', id);
      }
      threadIdRef.current = id;
    }
    return threadIdRef.current;
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    document.documentElement.className = isDark ? '' : 'light';
  }, [isDark]);

  async function sendMessage(message: string) {
    if (!message.trim() || loading) return;

    setMessages(prev => [...prev, { role: 'user', content: message }]);
    setLoading(true);
    setInput('');

    const command = message.trim().toLowerCase();

    if (command.startsWith('reset')) {
      try {
        const res = await fetch(`${API_BASE}/reset`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_input: message, thread_id: getThreadId() }),
        });
        const text = await res.text();
        setMessages(prev => [...prev, { role: 'assistant', content: text }]);
      } catch {
        setMessages(prev => [...prev, { role: 'assistant', content: '❌ Something went wrong. Please try again.' }]);
      }
      setLoading(false);
      inputRef.current?.focus();
      return;
    }

    if (command.startsWith('no ') || command.startsWith('skip ')) {
    try {
      const res = await fetch(`${API_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback: message, thread_id: getThreadId() }),
      });
      const text = await res.text();
      setMessages(prev => [...prev, { role: 'assistant', content: text }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ Something went wrong. Please try again.' }]);
    }
    setLoading(false);
    inputRef.current?.focus();
    return;
    }

    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: message, thread_id: getThreadId() }),
      });
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1].content += chunk;
          return updated;
        });
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ Something went wrong. Please try again.' }]);
    }

    setLoading(false);
    inputRef.current?.focus();
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('thread_id', getThreadId());

    setMessages(prev => [...prev, { role: 'user', content: `📄 Uploaded: ${file.name}` }]);

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1].content += chunk;
          return updated;
        });
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ Failed to upload CV. Please try again.' }]);
    }

    setLoading(false);
    e.target.value = '';
  }

  return (
    <div className="min-h-screen flex flex-col bg-[var(--background)] text-[var(--foreground)]">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-[var(--card-border)] bg-[var(--card-bg)]/80 backdrop-blur-md">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight">Job Search Agent</h1>
              <p className="text-xs text-[var(--muted)]">AI-powered remote job finder</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle isDark={isDark} onToggle={() => setIsDark(d => !d)} />
          </div>
        </div>
      </header>

      {/* Chat area */}
      <main className="flex-1 overflow-hidden">
        <div className="max-w-3xl mx-auto h-full flex flex-col">
          <div className="flex-1 overflow-y-auto chat-scroll px-4 py-6 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="w-16 h-16 rounded-2xl bg-emerald-600/10 border border-emerald-600/20 flex items-center justify-center mb-4">
                  <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                </div>
                <h2 className="text-xl font-bold mb-2">Find Your Next Remote Job</h2>
                <p className="text-[var(--muted)] max-w-md text-sm leading-relaxed mb-6">
                  Describe your ideal job and I&apos;ll search for matching positions.
                  You can also upload your CV for personalized results.
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {['Remote React jobs', 'Python backend roles in EU', 'No MERN stack'].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => sendMessage(suggestion)}
                      className="px-3 py-1.5 text-sm rounded-full border border-[var(--card-border)] hover:border-emerald-600/50 hover:bg-emerald-600/5 transition-colors text-[var(--muted)] hover:text-emerald-400"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-3 ${
                    m.role === 'user'
                      ? 'bg-[var(--user-bubble)] rounded-br-md'
                      : 'bg-[var(--assistant-bubble)] border border-[var(--card-border)] rounded-bl-md'
                  }`}
                >
                  <p className={`text-xs font-semibold mb-1.5 ${
                    m.role === 'user' ? 'text-emerald-300' : 'text-emerald-400'
                  }`}>
                    {m.role === 'user' ? 'You' : 'Agent'}
                  </p>
                  <div className={`prose prose-sm ${isDark ? 'prose-invert' : ''} max-w-none text-sm leading-relaxed`}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        ul: ({ ...props }) => <ul className="list-disc pl-4 space-y-1 my-2" {...props} />,
                        li: ({ ...props }) => <li className="text-sm leading-relaxed" {...props} />,
                        a: ({ ...props }) => (
                          <a
                            className="text-emerald-400 font-medium underline hover:text-emerald-300 transition-colors break-all"
                            target="_blank"
                            rel="noopener noreferrer"
                            {...props}
                          />
                        ),
                        code: ({ ...props }) => (
                          <code className="bg-black/20 px-1.5 py-0.5 rounded text-xs font-mono" {...props} />
                        ),
                        strong: ({ ...props }) => <strong className="font-bold text-[var(--foreground)]" {...props} />,
                      }}
                    >
                      {m.content}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            ))}

            {loading && messages[messages.length - 1]?.role !== 'assistant' && (
              <div className="flex justify-start">
                <div className="bg-[var(--assistant-bubble)] border border-[var(--card-border)] rounded-2xl rounded-bl-md">
                  <TypingIndicator />
                </div>
              </div>
            )}

            {loading && messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.content && (
              <div className="flex justify-start">
                <div className="bg-[var(--assistant-bubble)] border border-[var(--card-border)] rounded-2xl rounded-bl-md max-w-[75%]">
                  <SkeletonLoader />
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input area */}
          <div className="border-t border-[var(--card-border)] bg-[var(--card-bg)]/80 backdrop-blur-md px-4 py-3">
            <div className="max-w-3xl mx-auto flex items-center gap-2">
              <button
                className="shrink-0 p-2.5 rounded-xl border border-[var(--card-border)] hover:border-emerald-600/50 hover:bg-emerald-600/5 transition-colors text-[var(--muted)] hover:text-emerald-400"
                onClick={() => document.getElementById('fileInput')?.click()}
                title="Upload CV (PDF only)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
              </button>
              <input
                type="file"
                id="fileInput"
                className="hidden"
                accept=".pdf"
                onChange={handleFileUpload}
              />
              <div className="flex-1 flex items-center gap-2 bg-[var(--input-bg)] border border-[var(--input-border)] rounded-xl px-3 py-1 focus-within:border-emerald-600/50 focus-within:ring-1 focus-within:ring-emerald-600/20 transition-all">
                <input
                  ref={inputRef}
                  className="flex-1 bg-transparent py-1.5 text-sm outline-none placeholder:text-[var(--muted)]"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
                  placeholder="Search jobs or type 'no MERN' to filter..."
                  disabled={loading}
                />
                <button
                  className="shrink-0 p-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
                  onClick={() => sendMessage(input)}
                  disabled={loading || !input.trim()}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>
                </button>
              </div>
            </div>
            <p className="text-[10px] text-[var(--muted)] text-center mt-2">
              Upload your CV for personalized results &middot; Use &quot;no [keyword]&quot; to filter out unwanted results
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
