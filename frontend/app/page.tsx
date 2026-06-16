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
  const [threadId, setThreadId] = useState('')

        useEffect(() => {
      let id = localStorage.getItem('thread_id')
      if (!id) {
        id = crypto.randomUUID()
        localStorage.setItem('thread_id', id)
      }
      setThreadId(id)
    }, [])

    async function sendMessage(message: string) {
    setMessages(prev => [...prev, { role: 'user', content: message }])
    setLoading(true)
    if (message.startsWith('no ') || message.startsWith('skip ')) {
        await fetch('http://localhost:8000/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feedback: message, thread_id: threadId })
        })
        setMessages(prev => [...prev, { role: 'assistant', content: '✅ Got it! Filtering updated.' }])
        setLoading(false)
        setInput('')
        return
    }
    const res = await fetch('http://localhost:8000/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_input: message, thread_id: threadId })
        })
    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])
      while(true) {
        const { done, value } = await reader!.read()
        if(done) break
       const chunk = decoder.decode(value, { stream: true })
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
              <button
          className="px-4 py-2 bg-blue-500 text-white rounded-lg"
          onClick={() => document.getElementById('fileInput')?.click()}
        >
          📄 Upload CV (PDF only)
        </button>
       <input
        type="file"
        id="fileInput"
        className="hidden"
        accept=".pdf"
        onChange={async (e) => {
          const file = e.target.files?.[0]
          if (!file) return
          setLoading(true)
          const formData = new FormData()
          formData.append("file", file)
          formData.append("thread_id", threadId)
          const res = await fetch("http://localhost:8000/upload", {
            method: "POST",
            body: formData
          })
    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])
      while(true) {
        const { done, value } = await reader!.read()
        if(done) break
        const chunk = decoder.decode(value, { stream: true })
        setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1].content += chunk
            return updated
        })
    }
    setLoading(false)
    setInput('')
           }}
      />
          <input
            className="flex-1 p-2 rounded-lg bg-slate-800 border border-emerald-700 text-white"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage(input)}
            
            placeholder="Search jobs or type eg 'no MERN' to filter results"
            
          />
          
          <button className="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-white" onClick={() => sendMessage(input)}>
            Send
          </button>
        </div>
    </div>
)}   




