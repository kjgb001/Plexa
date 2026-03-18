import { useState, useEffect } from "react"
import { useApis } from "../api"
import type { Message, Session } from "../api/interfaces"


interface Props {
  courseId: string
  lessonId: string
  lessonVersion: string
  sessionId?: string | null
}

export default function ChatScreen({ courseId, lessonId, lessonVersion, sessionId = null }: Props) {
  const { sessionApi } = useApis()
  const [session, setSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [booting, setBooting] = useState(true)

  useEffect(() => {
    let active = true

    async function initSession() {
      const result = sessionId
        ? await sessionApi.getSession(
          courseId,
          lessonId,
          lessonVersion,
          sessionId
        )
        : await sessionApi.createSession(
          courseId,
          lessonId,
          lessonVersion
        )

      if (!active) {
        return
      }

      setSession(result.session)
      setMessages(result.messages)
      setBooting(false)
    }

    void initSession()

    return () => {
      active = false
    }
  }, [courseId, lessonId, lessonVersion, sessionApi, sessionId])

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
      const result = await sessionApi.sendMessage(input, sessionId)

      setMessages(prev => [
        ...prev,
        result.assistantMessage
      ])

      setSession(result.session)
    } finally {
      setLoading(false)
    }
  }

  if (!session || booting) {
    return (
      <section className="screen-card">
        <p className="eyebrow">Conversation</p>
        <h1>Preparing workspace</h1>
        <p>Starting lesson session and loading transcript...</p>
      </section>
    )
  }

  return (
    <section className="screen-card chat-layout">
      <div className="screen-card__header">
        <div>
          <p className="eyebrow">Conversation</p>
          <h1>Lesson chat</h1>
          <p>
            Work inside the lesson context, ask questions, test ideas, and watch
            the transcript accumulate as a structured learning artifact.
          </p>
        </div>
        <div className="screen-card__actions">
          <span className="section-chip">
            Turn {session.turn_count} / {session.max_turns}
          </span>
          <span className="section-chip">
            {session.is_active ? "Active" : "Closed"}
          </span>
        </div>
      </div>

      <div className="transcript">
        <div className="transcript__stack">
          {messages.map((msg, index) => (
            <article
              key={`${msg.role}:${index}:${msg.content.slice(0, 20)}`}
              className={`message-card message-card--${msg.role}`}
            >
              <span className="message-role">{msg.role}</span>
              <p className="message-body">{msg.content}</p>
            </article>
          ))}
        </div>
      </div>

      <div className="composer">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask a question, test a prompt, or reflect on the lesson."
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              void sendMessage()
            }
          }}
        />

        <button
          className="composer-button"
          onClick={() => void sendMessage()}
          disabled={loading || !session.is_active}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </div>
    </section>
  )
}
