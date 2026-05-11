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

function dispatchSessionChanged(courseId: string, lessonId: string, lessonVersion: string) {
  window.dispatchEvent(
    new CustomEvent("plexa:sessions-changed", {
      detail: { courseId, lessonId, lessonVersion },
    }),
  )
}

export default function ChatScreen({
  courseId,
  lessonId,
  lessonVersion,
  sessionId = null,
}: Props) {
  const { sessionApi } = useApis()
  const transcriptRef = useRef<HTMLOListElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
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
  const visibleMessages = messages.filter((message) => message.role !== "system")

  useEffect(() => {
    latestSessionRef.current = session
    latestMessagesRef.current = messages
    latestLoadingRef.current = loading
  }, [loading, messages, session])

  useEffect(() => {
    let active = true

    async function loadSession() {
      if (sessionId === null) {
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

        if (active) {
          setSession(result.session)
          setMessages(result.messages)
        }
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

    if (element) {
      element.scrollTop = element.scrollHeight
    }
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
        sessionIdAtMount === null ||
        suppressAutoDeleteRef.current ||
        currentSession === null ||
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
      const result = await sessionApi.createSession(courseId, lessonId, lessonVersion)
      dispatchSessionChanged(courseId, lessonId, lessonVersion)

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
    if (session === null) {
      return
    }

    setDeleting(true)
    setInteractionError(null)

    try {
      suppressAutoDeleteRef.current = true
      await sessionApi.deleteSession(courseId, lessonId, lessonVersion, session.session_id)
      dispatchSessionChanged(courseId, lessonId, lessonVersion)
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
    if (session === null || input.trim() === "" || loading || session.is_active === false) {
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
      dispatchSessionChanged(courseId, lessonId, lessonVersion)
    } catch (error) {
      console.error("Failed to send message", error)
      setMessages((previous) => previous.slice(0, -1))
      setInput(content)
      setInteractionError("Message delivery failed. Try again.")
    } finally {
      setLoading(false)
      requestAnimationFrame(() => {
        inputRef.current?.focus()
      })
    }
  }

  if (sessionId === null) {
    return (
      <section className="conversation-stage conversation-stage--empty" aria-labelledby="conversation-empty-title">
        <header className="conversation-stage__hero">
          <p className="eyebrow">Conversation</p>
          <h1 id="conversation-empty-title">Start a lesson session</h1>
          <p className="conversation-stage__summary">
            The lesson stays fixed while sessions hold each separate attempt. Open
            an older conversation from the rail or create a new workspace here.
          </p>
        </header>

        <section className="conversation-stage__empty-card">
          <h2>Ready to begin?</h2>
          <p>
            New sessions are lightweight. If you leave before sending a message,
            Plexa will automatically clean that session up.
          </p>
          <button
            className="primary-button conversation-stage__primary"
            onClick={() => void handleCreateSession()}
            disabled={creating}
          >
            {creating ? "Starting..." : "Start new session"}
          </button>
          {bootError ? <p className="empty-panel">{bootError}</p> : null}
        </section>
      </section>
    )
  }

  if (booting) {
    return (
      <section className="conversation-stage conversation-stage--empty">
        <header className="conversation-stage__hero">
          <p className="eyebrow">Conversation</p>
          <h1>Preparing workspace</h1>
          <p className="conversation-stage__summary">
            Loading transcript and session state...
          </p>
        </header>
      </section>
    )
  }

  if (session === null) {
    return (
      <section className="conversation-stage conversation-stage--empty">
        <header className="conversation-stage__hero">
          <p className="eyebrow">Conversation</p>
          <h1>Session unavailable</h1>
          <p className="conversation-stage__summary">
            {bootError ?? "This session could not be loaded."}
          </p>
        </header>
      </section>
    )
  }

  return (
    <>
      <section className="conversation-stage" aria-label="Lesson conversation">
        <header className="conversation-stage__hero conversation-stage__hero--tight conversation-stage__hero--meta-only">
          <div className="conversation-stage__meta">
            <dl className="conversation-stage__stats" aria-label="Session details">
              <div>
                <dt>Turns</dt>
                <dd>{session.turn_count} / {session.max_turns}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{session.is_active ? "Active" : "Closed"}</dd>
              </div>
            </dl>
            <button
              className="ghost-button ghost-button--danger"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={deleting || loading}
            >
              Delete session
            </button>
          </div>
        </header>

        <section className="conversation-stage__frame" aria-label="Conversation transcript">
          <ol ref={transcriptRef} className="transcript transcript-list" aria-label="Messages">
            {session.is_active === false ? (
              <li>
                <p className="empty-panel">
                  This session is closed. Review it here or start a new one from the left rail.
                </p>
              </li>
            ) : null}

            {session.turn_count === 0 ? (
              <li>
                <p className="empty-panel">
                  Leave this session without sending a message and it will be deleted automatically.
                </p>
              </li>
            ) : null}

            {interactionError ? (
              <li>
                <p className="empty-panel">{interactionError}</p>
              </li>
            ) : null}

            {visibleMessages.map((message, index) => (
              <li key={`${message.role}:${index}:${message.content.slice(0, 24)}`}>
                <article className={`transcript-entry transcript-entry--${message.role}`}>
                  <header className="transcript-entry__header">
                    <span className="transcript-entry__role">{message.role}</span>
                  </header>
                  <p className="message-body">{message.content}</p>
                </article>
              </li>
            ))}

            {loading ? (
              <li>
                <article className="transcript-entry transcript-entry--assistant transcript-entry--pending">
                  <header className="transcript-entry__header">
                    <span className="transcript-entry__role">assistant</span>
                  </header>
                  <p className="message-body">Thinking...</p>
                </article>
              </li>
            ) : null}
          </ol>

          <form
            className="composer composer-form"
            onSubmit={(event) => {
              event.preventDefault()
              void sendMessage()
            }}
          >
            <label className="composer-form__field">
              <span className="sr-only">Message</span>
              <input
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask a question, test a prompt, or reflect on the lesson."
                disabled={loading || deleting || session.is_active === false}
              />
            </label>

            <button
              className="composer-button"
              type="submit"
              disabled={loading || deleting || session.is_active === false || input.trim() === ""}
            >
              {loading ? "Sending..." : "Send"}
            </button>
          </form>
        </section>
      </section>

      {showDeleteConfirm ? (
        <aside className="modal-backdrop" aria-hidden="true">
          <section
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-session-title"
          >
            <p className="eyebrow">Confirm Action</p>
            <h2 id="delete-session-title">Delete this session?</h2>
            <p>
              This permanently removes the transcript and session state for this lesson conversation.
            </p>
            <footer className="modal-actions">
              <button
                className="ghost-button"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                onClick={() => void handleDeleteSession()}
                disabled={deleting}
              >
                {deleting ? "Deleting..." : "Delete session"}
              </button>
            </footer>
          </section>
        </aside>
      ) : null}
    </>
  )
}
