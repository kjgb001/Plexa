import { useState } from "react"
import { sessionApi } from "../api"
import type { Message, Session } from "../api/types"

export default function ChatScreen() {
  const [session, setSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)

  async function startSession() {
    const result = await sessionApi.createSession(
      "CS101",
      "test",
      "0.1.0"
    )

    setSession(result.session)
    setMessages(result.session.messages ?? [])
  }

  async function sendMessage() {
    if (!session || !input.trim()) return

    const userMessage: Message = {
      role: "user",
      content: input
    }

    setMessages(prev => [...prev, userMessage])
    setInput("")
    setLoading(true)

    try {
      const result = await sessionApi.sendMessage(session.session_id, input)

      setMessages(prev => [
        ...prev,
        result.assistant_message
      ])

      setSession(result.session)
    } finally {
      setLoading(false)
    }
  }

  if (!session) {
    return (
      <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
        <h1>Plexa Chat</h1>
        <button onClick={startSession}>Start Session</button>
      </div>
    )
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa Chat</h1>

      <div
        style={{
          border: "1px solid #ccc",
          padding: "1rem",
          height: "400px",
          overflowY: "auto",
          marginBottom: "1rem"
        }}
      >
        {messages.map((msg, i) => (
          <div key={i}>
            <strong>{msg.role}:</strong> {msg.content}
          </div>
        ))}
      </div>

      <input
        value={input}
        onChange={e => setInput(e.target.value)}
        placeholder="Type a message"
      />

      <button onClick={sendMessage} disabled={loading}>
        Send
      </button>
    </div>
  )
}