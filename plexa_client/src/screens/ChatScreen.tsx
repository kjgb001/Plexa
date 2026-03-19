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
  const latestSessionRef = useRef<Session | null>(null)
  const latestMessagesRef = useRef<Message[]>([])
  const latestLoadingRef = useRef(false)
  const suppressAutoDeleteRef = useRef(false)
  const [session, setSession] = useState<Session | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [booting, setBooting] = useState(false)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [bootError, setBootError] = useState<string | null>(null)
  const [interactionError, setInteractionError] = useState<string | null>(null)

  useEffect(() => {
    latestSessionRef.current = session
    latestMessagesRef.current = messages
    latestLoadingRef.current = loading
  }, [loading, messages, session])

  useEffect(() => {
    let active = true

    async function loadSession() {
      if (!sessionId) {
        setSession(null)
        setMessages([])
        setInput("")
        setShowDeleteConfirm(false)
        setBootError(null)
        setInteractionError(null)
        setBooting(false)
        return
      }

      setBooting(true)
      setBootError(null)
      setInteractionError(null)
      setShowDeleteConfirm(false)

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

  useEffect(() => {
    const sessionIdAtMount = sessionId
    const courseIdAtMount = courseId
    const lessonIdAtMount = lessonId
    const lessonVersionAtMount = lessonVersion

    return () => {
      const currentSession = latestSessionRef.current
      const currentMessages = latestMessagesRef.current
      const currentLoading = latestLoadingRef.current
      const hasUserMessages = currentMessages.some((message) => message.role === "user")

      if (
        !sessionIdAtMount ||
        suppressAutoDeleteRef.current ||
        !currentSession ||
        currentSession.session_id !== sessionIdAtMount ||
        currentSession.turn_count > 0 ||
        hasUserMessages ||
        currentLoading
      ) {
        return
      }

      void sessionApi.deleteSession(
        courseIdAtMount,
        lessonIdAtMount,
        lessonVersionAtMount,
        sessionIdAtMount,
      )
    }
  }, [courseId, lessonId, lessonVersion, sessionApi, sessionId])

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

  async function handleDeleteSession() {
    if (!session) {
      return
    }

    setDeleting(true)
    setInteractionError(null)

    try {
      suppressAutoDeleteRef.current = true
      await sessionApi.deleteSession(
        courseId,
        lessonId,
        lessonVersion,
        session.session_id,
      )
      setShowDeleteConfirm(false)
      navigate(
        `/app/courses/${encodeURIComponent(courseId)}/lessons/${encodeURIComponent(lessonId)}/${encodeURIComponent(lessonVersion)}`,
      )
    } catch (error) {
      console.error("Failed to delete session", error)
      suppressAutoDeleteRef.current = false
      setInteractionError("Session deletion failed. Try again.")
    } finally {
      setDeleting(false)
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
    <>
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
            <button
              className="ghost-button ghost-button--danger"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={deleting || loading}
            >
              Delete session
            </button>
          </div>
        </div>

        {!session.is_active ? (
          <div className="empty-panel">
            This session is closed. Review it here or start a new session from the
            left rail.
          </div>
        ) : null}

        {session.turn_count === 0 ? (
          <div className="empty-panel">
            Leave this session without sending a message and it will be deleted
            automatically.
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
            disabled={loading || deleting || !session.is_active}
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
            disabled={loading || deleting || !session.is_active || !input.trim()}
          >
            {loading ? "Sending..." : "Send"}
          </button>
        </div>
      </section>

      {showDeleteConfirm ? (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-session-title"
          >
            <p className="eyebrow">Confirm Action</p>
            <h2 id="delete-session-title">Delete this session?</h2>
            <p>
              This will permanently remove the transcript and session state for
              this lesson conversation.
            </p>
            <div className="modal-actions">
              <button
                className="ghost-button"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                className="primary-button primary-button--danger"
                onClick={() => void handleDeleteSession()}
                disabled={deleting}
              >
                {deleting ? "Deleting..." : "Delete session"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
