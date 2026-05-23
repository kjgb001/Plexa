import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import { useApis } from "../api"
import type { Lesson, Message, Session, SessionReflectionHook } from "../api/interfaces"
import { navigate, studentPaths } from "../app/router"

interface Props {
  courseId: string
  lessonId: string
  lessonVersion: string
  lessonTitle?: string
  lesson?: Lesson | null
  sessionId?: string | null
}

const MAX_COMPOSER_HEIGHT_PX = 224

function dispatchSessionChanged(
  courseId: string,
  lessonId: string,
  lessonVersion: string,
  change: { type: "upsert"; session: Session } | { type: "delete"; sessionId: string },
) {
  window.dispatchEvent(
    new CustomEvent("plexa:sessions-changed", {
      detail: { courseId, lessonId, lessonVersion, change },
    }),
  )
}

export default function ChatScreen({
  courseId,
  lessonId,
  lessonVersion,
  lessonTitle,
  lesson = null,
  sessionId = null,
}: Props) {
  const { sessionApi } = useApis()
  const transcriptRef = useRef<HTMLOListElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const latestSessionRef = useRef<Session | null>(null)
  const latestMessagesRef = useRef<Message[]>([])
  const latestLoadingRef = useRef(false)
  const suppressAutoDeleteRef = useRef(false)
  const keepComposerFocusRef = useRef(true)
  const suppressComposerBlurRef = useRef(false)
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
  const [reflectionDrafts, setReflectionDrafts] = useState<Record<string, string>>({})
  const [collapsedReflectionIds, setCollapsedReflectionIds] = useState<Record<string, boolean>>({})
  const [isReflectionDrawerOpen, setIsReflectionDrawerOpen] = useState(false)
  const visibleMessages = messages.filter((message) => message.role !== "system")
  const latestNonUserMessageIndex = (() => {
    for (let index = visibleMessages.length - 1; index >= 0; index -= 1) {
      if (visibleMessages[index].role !== "user") {
        return index
      }
    }
    return -1
  })()
  const triggeredReflectionHooks = useMemo(
    () =>
      [...(session?.reflection_hooks ?? [])]
        .filter((hook) => hook.triggered_at)
        .sort((left, right) => left.order_index - right.order_index),
    [session],
  )
  const triggeredReflectionKey = triggeredReflectionHooks
    .map((hook) => `${hook.hook_id}:${hook.triggered_at ?? ""}`)
    .join("|")
  const allTriggeredReflectionsSaved = triggeredReflectionHooks.every(
    (hook) => Boolean(hook.response_text?.trim()) && collapsedReflectionIds[hook.hook_id] === true,
  )
  const triggeredMidReflectionHooks = triggeredReflectionHooks.filter((hook) => hook.phase === "mid")
  const triggeredPostReflectionHooks = triggeredReflectionHooks.filter((hook) => hook.phase !== "mid")
  const hasBlockingMidReflection = triggeredMidReflectionHooks.some((hook) => !hook.response_text?.trim())
  const visibleMidReflectionHooks = triggeredMidReflectionHooks.filter((hook) => collapsedReflectionIds[hook.hook_id] !== true)
  const visiblePostReflectionHooks = triggeredPostReflectionHooks.filter((hook) => collapsedReflectionIds[hook.hook_id] !== true)
  const collapsedMidReflectionHooks = triggeredMidReflectionHooks.filter((hook) => collapsedReflectionIds[hook.hook_id] === true)
  const collapsedPostReflectionHooks = triggeredPostReflectionHooks.filter((hook) => collapsedReflectionIds[hook.hook_id] === true)
  const collapsedReflectionHooks = [...collapsedMidReflectionHooks, ...collapsedPostReflectionHooks]
  const composerDisabled = deleting || session?.is_active === false || session?.is_finalized || session?.is_completion_started || hasBlockingMidReflection

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

      keepComposerFocusRef.current = true

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
          setReflectionDrafts(
            Object.fromEntries(
              result.session.reflection_hooks.map((hook) => [hook.hook_id, hook.response_text ?? ""]),
            ),
          )
          setCollapsedReflectionIds(
            Object.fromEntries(
              result.session.reflection_hooks
                .filter((hook) => hook.response_text?.trim())
                .map((hook) => [hook.hook_id, true]),
            ),
          )
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
  }, [messages, loading, triggeredReflectionKey])

  function focusComposerIfAllowed(force = false) {
    if (!force && keepComposerFocusRef.current === false) {
      return
    }

    requestAnimationFrame(() => {
      const element = inputRef.current
      if (element === null || element.disabled) {
        return
      }
      element.focus()
    })
  }

  useLayoutEffect(() => {
    const element = inputRef.current
    if (!element) {
      return
    }

    element.style.height = "0px"
    const nextHeight = Math.min(element.scrollHeight, MAX_COMPOSER_HEIGHT_PX)
    element.style.height = `${nextHeight}px`
    element.style.overflowY = element.scrollHeight > MAX_COMPOSER_HEIGHT_PX ? "auto" : "hidden"

    const transcript = transcriptRef.current
    if (transcript) {
      transcript.scrollTop = transcript.scrollHeight
    }
  }, [input])

  useEffect(() => {
    if (
      sessionId !== null &&
      session !== null &&
      booting === false &&
      deleting === false
    ) {
      keepComposerFocusRef.current = true
      focusComposerIfAllowed(true)
    }
  }, [booting, deleting, session, sessionId])

  useEffect(() => {
    if (session === null) {
      setReflectionDrafts({})
      setCollapsedReflectionIds({})
      setIsReflectionDrawerOpen(false)
      return
    }
    setReflectionDrafts((current) => {
      const next: Record<string, string> = {}
      for (const hook of session.reflection_hooks) {
        next[hook.hook_id] = current[hook.hook_id] ?? hook.response_text ?? ""
      }
      return next
    })
    setCollapsedReflectionIds((current) => {
      const next: Record<string, boolean> = {}
      for (const hook of session.reflection_hooks) {
        if (hook.response_text?.trim()) {
          next[hook.hook_id] = current[hook.hook_id] ?? true
        }
      }
      return next
    })
  }, [session])

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
      keepComposerFocusRef.current = true
      dispatchSessionChanged(courseId, lessonId, lessonVersion, {
        type: "upsert",
        session: result.session,
      })

      navigate(studentPaths.session(courseId, lessonId, lessonVersion, result.session.session_id))
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
      dispatchSessionChanged(courseId, lessonId, lessonVersion, {
        type: "delete",
        sessionId: session.session_id,
      })
      setShowDeleteConfirm(false)
      navigate(studentPaths.chat(courseId, lessonId, lessonVersion))
    } catch (error) {
      console.error("Failed to delete session", error)
      suppressAutoDeleteRef.current = false
      setInteractionError("Session deletion failed. Try again.")
    } finally {
      setDeleting(false)
    }
  }

  async function handleBeginCompletion() {
    if (session === null) {
      return
    }
    setInteractionError(null)
    setLoading(true)
    try {
      const result = await sessionApi.beginCompletion(courseId, lessonId, lessonVersion, session.session_id)
      setSession(result.session)
      dispatchSessionChanged(courseId, lessonId, lessonVersion, {
        type: "upsert",
        session: result.session,
      })
    } catch (error) {
      console.error("Failed to begin completion", error)
      setInteractionError("Could not start completion right now.")
    } finally {
      setLoading(false)
    }
  }

  async function handleResumeWork() {
    if (session === null) {
      return
    }
    setInteractionError(null)
    setLoading(true)
    try {
      const result = await sessionApi.resumeAfterCompletion(courseId, lessonId, lessonVersion, session.session_id)
      setSession(result.session)
      dispatchSessionChanged(courseId, lessonId, lessonVersion, {
        type: "upsert",
        session: result.session,
      })
      focusComposerIfAllowed(true)
    } catch (error) {
      console.error("Failed to resume work", error)
      setInteractionError("Could not return this session to work mode.")
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveReflection(hook: SessionReflectionHook) {
    if (session === null) {
      return
    }
    const responseText = reflectionDrafts[hook.hook_id] ?? ""
    setInteractionError(null)
    setLoading(true)
    try {
      const result = await sessionApi.saveReflectionResponse(
        courseId,
        lessonId,
        lessonVersion,
        session.session_id,
        hook.hook_id,
        responseText,
      )
      setSession(result.session)
      setCollapsedReflectionIds((current) => ({
        ...current,
        [hook.hook_id]: true,
      }))
      setIsReflectionDrawerOpen(false)
      dispatchSessionChanged(courseId, lessonId, lessonVersion, {
        type: "upsert",
        session: result.session,
      })
    } catch (error) {
      console.error("Failed to save reflection", error)
      setInteractionError("Could not save that reflection response.")
    } finally {
      setLoading(false)
    }
  }

  async function handleTurnIn() {
    if (session === null) {
      return
    }
    setInteractionError(null)
    setLoading(true)
    try {
      const result = await sessionApi.turnInSession(courseId, lessonId, lessonVersion, session.session_id)
      setSession(result.session)
      dispatchSessionChanged(courseId, lessonId, lessonVersion, {
        type: "upsert",
        session: result.session,
      })
    } catch (error) {
      console.error("Failed to turn in session", error)
      setInteractionError("Could not turn this session in yet.")
    } finally {
      setLoading(false)
    }
  }

  async function sendMessage() {
    if (
      session === null ||
      input.trim() === "" ||
      loading ||
      session.is_active === false ||
      session.is_finalized ||
      session.is_completion_started ||
      hasBlockingMidReflection
    ) {
      if (hasBlockingMidReflection) {
        setInteractionError("Save the mid-session reflection before continuing the chat.")
      }
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
    suppressComposerBlurRef.current = true
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
      dispatchSessionChanged(courseId, lessonId, lessonVersion, {
        type: "upsert",
        session: result.session,
      })
    } catch (error) {
      console.error("Failed to send message", error)
      setMessages((previous) => previous.slice(0, -1))
      setInput(content)
      setInteractionError("Message delivery failed. Try again.")
    } finally {
      setLoading(false)
      focusComposerIfAllowed()
      requestAnimationFrame(() => {
        suppressComposerBlurRef.current = false
      })
    }
  }

  function renderReflectionHook(hook: SessionReflectionHook) {
    const responseText = reflectionDrafts[hook.hook_id] ?? ""

    return (
      <article className={`transcript-entry transcript-entry--system transcript-entry--reflection transcript-entry--reflection-${hook.phase}`}>
        <header className="transcript-entry__header">
          <span className="transcript-entry__role">
            Reflection prompt
          </span>
        </header>
        <h3 className="transcript-entry__title">
          {hook.phase === "mid" ? "Mid-session reflection" : "Post-completion reflection"}
        </h3>
        <p className="message-body">{hook.prompt}</p>
        <label className="composer-form__field transcript-entry__response">
          <span className="sr-only">Reflection response</span>
          <textarea
            value={responseText}
            onChange={(event) =>
              setReflectionDrafts((current) => ({
                ...current,
                [hook.hook_id]: event.target.value,
              }))
            }
            disabled={loading || session?.is_finalized}
            rows={3}
            placeholder="Write your reflection response here."
          />
        </label>
        {!session?.is_finalized ? (
          <div className="portal-inline-actions">
            <button className="ghost-button" type="button" onClick={() => void handleSaveReflection(hook)} disabled={loading}>
              Save reflection
            </button>
          </div>
        ) : null}
      </article>
    )
  }

  function renderReflectionDrawer(hooks: SessionReflectionHook[]) {
    if (hooks.length === 0) {
      return null
    }

    return (
      <article className={`reflection-drawer${isReflectionDrawerOpen ? " reflection-drawer--open" : ""}`}>
        <button
          className="reflection-drawer__toggle"
          type="button"
          aria-expanded={isReflectionDrawerOpen}
          aria-label={`${isReflectionDrawerOpen ? "Hide" : "Show"} saved reflections`}
          onClick={() => setIsReflectionDrawerOpen((current) => !current)}
        >
          <span className="reflection-drawer__arrow" aria-hidden="true">
            {isReflectionDrawerOpen ? "▾" : "▸"}
          </span>
          <span>Reflections</span>
        </button>

        {isReflectionDrawerOpen ? (
          <div className="reflection-drawer__items">
            {hooks.map((hook) => (
              <article className={`reflection-drawer__item reflection-drawer__item--${hook.phase}`} key={`saved-reflection:${hook.hook_id}`}>
                <div className="reflection-drawer__body">
                  <span className="reflection-drawer__label">
                    {hook.phase === "mid" ? "Saved mid-session reflection" : "Saved post-completion reflection"}
                  </span>
                  <p>{(reflectionDrafts[hook.hook_id] ?? "").trim() || hook.response_text || "Reflection saved."}</p>
                </div>
                {!session?.is_finalized ? (
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() =>
                      setCollapsedReflectionIds((current) => ({
                        ...current,
                        [hook.hook_id]: false,
                      }))
                    }
                  >
                    Review
                  </button>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
      </article>
    )
  }

  if (sessionId === null) {
    return (
      <section className="conversation-stage conversation-stage--empty lesson-overview-stage" aria-labelledby="conversation-empty-title">
        <header className="conversation-stage__hero">
          <p className="eyebrow">Lesson Workspace</p>
          <h1 id="conversation-empty-title">{lesson?.title ?? lessonTitle ?? lessonId}</h1>
          <p className="conversation-stage__summary">
            {lesson?.learning_objective ??
              "Review the lesson details, then start a new workspace or open a prior session from the sidebar."}
          </p>
        </header>

        <section className="lesson-overview-card">
          <div className="lesson-overview-card__primary">
            <p className="eyebrow">Selected Lesson</p>
            <h2>{lesson?.behavioral_focus ?? "Session setup"}</h2>
            <p>
              New sessions are lightweight. If you leave before sending a message,
              Plexa will automatically clean that session up.
            </p>
            <div className="portal-inline-actions">
              <button
                className="primary-button"
                onClick={() => void handleCreateSession()}
                disabled={creating}
              >
                {creating ? "Starting..." : "Start new session"}
              </button>
            </div>
          </div>

          <dl className="lesson-overview-card__facts">
            <div>
              <dt>Version</dt>
              <dd>v{lesson?.version ?? lessonVersion}</dd>
            </div>
            <div>
              <dt>Author</dt>
              <dd>{lesson?.author ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>Difficulty</dt>
              <dd>{lesson?.difficulty ?? "Flexible"}</dd>
            </div>
            <div>
              <dt>Duration</dt>
              <dd>{lesson?.approximate_time ?? "Flexible pace"}</dd>
            </div>
          </dl>

          {lesson?.tags?.length ? (
            <div className="tag-row lesson-overview-card__tags">
              {lesson.tags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
          ) : null}

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
            <div className="conversation-stage__meta-copy">
              <p className="eyebrow">Lesson</p>
              <h2>{lessonTitle ?? lessonId}</h2>
            </div>
            <div className="conversation-stage__meta-actions">
              <dl className="conversation-stage__stats" aria-label="Session details">
                <div>
                  <dt>Turns</dt>
                  <dd>{session.turn_count} / {session.max_turns}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>
                    {session.is_finalized
                      ? "Turned in"
                      : session.is_completion_started
                        ? "Completion in progress"
                        : session.is_active
                          ? "Active"
                          : "Closed"}
                  </dd>
                </div>
              </dl>
              <div className="conversation-stage__completion-actions" aria-label="Completion actions">
                {session.is_finalized ? (
                  <button className="primary-button" type="button" disabled>
                    Locked
                  </button>
                ) : null}
                {!session.is_finalized && !session.is_completion_started ? (
                  <button className="ghost-button" type="button" onClick={() => void handleBeginCompletion()} disabled={loading || deleting}>
                    Complete work
                  </button>
                ) : null}
                {!session.is_finalized && session.is_completion_started && session.is_active ? (
                  <button className="ghost-button" type="button" onClick={() => void handleResumeWork()} disabled={loading || deleting}>
                    Keep working
                  </button>
                ) : null}
                {!session.is_finalized && session.is_completion_started ? (
                  <button className="primary-button" type="button" onClick={() => void handleTurnIn()} disabled={loading || deleting || !allTriggeredReflectionsSaved}>
                    Turn in
                  </button>
                ) : null}
              </div>
              <button
                className="ghost-button ghost-button--danger"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={deleting || loading}
              >
                Delete session
              </button>
            </div>
          </div>
        </header>

        <section className="conversation-stage__frame" aria-label="Conversation transcript">
          <ol ref={transcriptRef} className="transcript transcript-list" aria-label="Messages">
            {session.is_active === false && session.is_finalized === false ? (
              <li>
                <p className="empty-panel">
                  Chat is closed for this session. You can still complete reflections and turn in your work.
                </p>
              </li>
            ) : null}

            {session.is_finalized ? (
              <li>
                <p className="empty-panel">
                  This session has been turned in and locked.
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
                {index === latestNonUserMessageIndex && (visibleMidReflectionHooks.length > 0 || collapsedReflectionHooks.length > 0) ? (
                  <div className="reflection-drawer-stack">
                    {visibleMidReflectionHooks.map((hook) => (
                      <div key={`mid-reflection:${hook.hook_id}`}>
                        {renderReflectionHook(hook)}
                      </div>
                    ))}
                    {renderReflectionDrawer(collapsedReflectionHooks)}
                  </div>
                ) : null}
              </li>
            ))}

            {latestNonUserMessageIndex === -1 && visibleMidReflectionHooks.map((hook) => (
              <li key={`reflection:${hook.hook_id}`}>
                {renderReflectionHook(hook)}
              </li>
            ))}

            {latestNonUserMessageIndex === -1 && collapsedReflectionHooks.length > 0 ? (
              <li className="transcript-list__compact-item">
                {renderReflectionDrawer(collapsedReflectionHooks)}
              </li>
            ) : null}

            {visiblePostReflectionHooks.map((hook) => (
              <li key={`reflection:${hook.hook_id}`}>
                {renderReflectionHook(hook)}
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
              <textarea
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onFocus={() => {
                  keepComposerFocusRef.current = true
                }}
                onBlur={() => {
                  if (suppressComposerBlurRef.current) {
                    return
                  }
                  requestAnimationFrame(() => {
                    const activeElement = document.activeElement
                    if (activeElement !== inputRef.current) {
                      keepComposerFocusRef.current = false
                    }
                  })
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault()
                    void sendMessage()
                  }
                }}
                placeholder="Ask a question, test a prompt, or reflect on the lesson."
                disabled={composerDisabled}
                rows={1}
              />
            </label>

            <button
              className="composer-button"
              type="submit"
              onMouseDown={(event) => {
                event.preventDefault()
              }}
              disabled={loading || composerDisabled || input.trim() === ""}
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
