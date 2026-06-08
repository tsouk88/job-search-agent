'use client';

import { useState, useEffect } from "react"
import ReactMarkdown from 'react-markdown'

type Message = {
  role: 'user' | 'assistant'
  content: string
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

    async function sendMessage(message: string) {
    setMessages(prev => [...prev, { role: 'user', content: message }])
    setLoading(true)
    const res = await fetch('http://localhost:8000/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_input: message })
    })
    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])
      while(true) {
        const { done, value } = await reader!.read()
        if(done) break
        const chunk = decoder.decode(value)
        setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1].content += chunk
            return updated
        })
    }
    setLoading(false)
    setInput('')
  }
  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Find A Remote Job</h1>

      <div className="w-full max-w-3xl flex flex-col gap-4 mb-4 h-[60vh] overflow-y-auto">
        {messages.map((m, i) => (
          <div key={i} className={`p-4 rounded-lg ${m.role === 'user' ? 'bg-emerald-900 ml-16' : 'bg-slate-800 mr-16'}`}>
        <p className="text-xs text-emerald-400 mb-1">{m.role === 'user' ? 'You' : 'Assistant'}</p>
        <ReactMarkdown
          components={{
            ul: ({node, ...props}) => <ul className="list-disc pl-4 space-y-1" {...props} />,
            li: ({node, ...props}) => <li className="text-sm" {...props} />,
          }}
        >
          {m.content}
        </ReactMarkdown>
        
      </div>
        ))}{loading && <p className="text-emerald-400 animate-pulse">Searching for jobs...</p>}
      </div>
            <div className="flex gap-2 w-full max-w-3xl">
              
          <input
            className="flex-1 p-2 rounded-lg bg-slate-800 border border-emerald-700 text-white"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage(input)}
            
            placeholder="Let's search jobs , give me keywords"
            
          />
          
          <button className="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-white" onClick={() => sendMessage(input)}>
            Send
          </button>
        </div>
    </div>
)}   




