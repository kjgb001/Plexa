import { useEffect, useRef, useState } from "react"
import { useApis } from "../api"
import type { Message, Session } from "../api/interfaces"
import { navigate } from "../app/router"

interface Props {
  courseId: string
  lessonId: string
  lessonVersion: string
  sessionId?: string | null
}

export default function ChatScreen({
  courseId,
  lessonId,
  lessonVersion,
  sessionId = null,
}: Props) {
  const { sessionApi } = useApis()
  const transcriptRef = useRef<HTMLDivElement | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [booting, setBooting] = useState(false)
  const [creating, setCreating] = useState(false)
  const [bootError, setBootError] = useState<string | null>(null)
  const [interactionError, setInteractionError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadSession() {
      if (!sessionId) {
        setSession(null)
        setMessages([])
        setBootError(null)
        setInteractionError(null)
        setBooting(false)
        return
      }

      setBooting(true)
      setBootError(null)

      try {
        const result = await sessionApi.getSession(
          courseId,
          lessonId,
          lessonVersion,
          sessionId,
        )

        if (!active) {
          return
        }

        setSession(result.session)
        setMessages(result.messages)
      } catch (error) {
        console.error("Failed to load session", error)

        if (active) {
          setSession(null)
          setMessages([])
          setBootError("Unable to load this session right now.")
        }
      } finally {
        if (active) {
          setBooting(false)
        }
      }
    }

    void loadSession()

    return () => {
      active = false
    }
  }, [courseId, lessonId, lessonVersion, sessionApi, sessionId])

  useEffect(() => {
    const element = transcriptRef.current

    if (!element) {
      return
    }

    element.scrollTop = element.scrollHeight
  }, [messages, loading])

  async function handleCreateSession() {
    setCreating(true)
    setBootError(null)
    setInteractionError(null)

    try {
      const result = await sessionApi.createSession(
        courseId,
        lessonId,
        lessonVersion,
      )

      navigate(
        `/app/courses/${encodeURIComponent(courseId)}/lessons/${encodeURIComponent(lessonId)}/${encodeURIComponent(lessonVersion)}/sessions/${encodeURIComponent(result.session.session_id)}`,
      )
    } catch (error) {
      console.error("Failed to create session", error)
      setBootError("Unable to start a new session right now.")
    } finally {
      setCreating(false)
    }
  }

  async function sendMessage() {
    if (!session || !input.trim() || loading || !session.is_active) {
      return
    }

    const content = input.trim()
    const userMessage: Message = {
      role: "user",
      content,
    }

    setInteractionError(null)
    setMessages((previous) => [...previous, userMessage])
    setInput("")
    setLoading(true)

    try {
      const result = await sessionApi.sendMessage(
        courseId,
        lessonId,
        lessonVersion,
        session.session_id,
        content,
      )

      setMessages((previous) => [...previous, result.assistantMessage])
      setSession(result.session)
    } catch (error) {
      console.error("Failed to send message", error)
      setMessages((previous) => previous.slice(0, -1))
      setInput(content)
      setInteractionError("Message delivery failed. Try again.")
    } finally {
      setLoading(false)
    }
  }

  if (!sessionId) {
    return (
      <section className="screen-card chat-layout">
        <div className="screen-card__header">
          <div>
            <p className="eyebrow">Conversation</p>
            <h1>Start a lesson session</h1>
            <p>
              Review the lesson context, then start a fresh session or reopen one
              from the history rail.
            </p>
          </div>
          <div className="screen-card__actions">
            <button
              className="primary-button"
              onClick={() => void handleCreateSession()}
              disabled={creating}
            >
              {creating ? "Starting..." : "Start new session"}
            </button>
          </div>
        </div>

        <div className="chat-empty-state">
          <div className="empty-panel">
            No session is active yet for this view. Start a new session to begin
            working, or select a prior session from the left rail.
          </div>
          {bootError ? <div className="empty-panel">{bootError}</div> : null}
        </div>
      </section>
    )
  }

  if (booting) {
    return (
      <section className="screen-card">
        <p className="eyebrow">Conversation</p>
        <h1>Preparing workspace</h1>
        <p>Loading transcript and lesson session state...</p>
      </section>
    )
  }

  if (!session) {
    return (
      <section className="screen-card">
        <p className="eyebrow">Conversation</p>
        <h1>Session unavailable</h1>
        <p>{bootError ?? "This session could not be loaded."}</p>
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
            Work inside the lesson context, ask questions, test ideas, and keep a
            reusable transcript for later reflection.
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

      {!session.is_active ? (
        <div className="empty-panel">
          This session is closed. Review it here or start a new session from the
          left rail.
        </div>
      ) : null}

      <div ref={transcriptRef} className="transcript">
        <div className="transcript__stack">
          {messages.map((message, index) => (
            <article
              key={`${message.role}:${index}:${message.content.slice(0, 24)}`}
              className={`message-card message-card--${message.role}`}
            >
              <span className="message-role">{message.role}</span>
              <p className="message-body">{message.content}</p>
            </article>
          ))}

          {loading ? (
            <article className="message-card message-card--assistant message-card--pending">
              <span className="message-role">assistant</span>
              <p className="message-body">Thinking...</p>
            </article>
          ) : null}
        </div>
      </div>

      {interactionError ? <div className="empty-panel">{interactionError}</div> : null}

      <div className="composer">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask a question, test a prompt, or reflect on the lesson."
          disabled={loading || !session.is_active}
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
          disabled={loading || !session.is_active || !input.trim()}
        >
          {loading ? "Sending..." : "Send"}
        </button>
      </div>
    </section>
  )
}
