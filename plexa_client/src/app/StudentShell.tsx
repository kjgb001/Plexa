import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react"
import { useApis } from "../api"
import type { Course, Lesson, Session } from "../api/interfaces"
import { useTheme } from "../theme/useTheme"
import { navigate, type AppRoute } from "./router"

interface StudentShellProps {
  route: Exclude<AppRoute, { kind: "login" | "auth-callback" | "not-found" }>
  userId: string | null
  onLogout(): Promise<void>
  children: ReactNode
}

function formatSessionTimestamp(value: string) {
  return new Date(value).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function sortSessionsByUpdatedAt(items: Session[]) {
  return [...items].sort((left, right) => {
    const delta = new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
    if (delta !== 0) {
      return delta
    }
    return right.session_id.localeCompare(left.session_id)
  })
}

function visibleRailItems<T>(
  items: T[],
  expanded: boolean,
  isSelected: (item: T) => boolean,
  limit = 4,
) {
  if (expanded || items.length <= limit) {
    return items
  }

  const selectedIndex = items.findIndex((item) => isSelected(item))
  if (selectedIndex === -1 || selectedIndex < limit) {
    return items.slice(0, limit)
  }

  return [...items.slice(0, limit - 1), items[selectedIndex]]
}

export default function StudentShell({
  route,
  userId,
  onLogout,
  children,
}: StudentShellProps) {
  const { courseApi, sessionApi } = useApis()
  const { theme, toggleTheme } = useTheme()
  const railScrollRef = useRef<HTMLDivElement | null>(null)
  const pendingPrependCompensationRef = useRef<{
    previousScrollHeight: number
    previousScrollTop: number
  } | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [lessonsLoading, setLessonsLoading] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [sessionPendingDelete, setSessionPendingDelete] = useState<Session | null>(null)
  const [sessionDeleting, setSessionDeleting] = useState(false)
  const [sessionCreating, setSessionCreating] = useState(false)
  const [coursesExpanded, setCoursesExpanded] = useState(false)
  const [lessonsExpanded, setLessonsExpanded] = useState(false)
  const [sessionsExpanded, setSessionsExpanded] = useState(false)

  const selectedCourseId = route.kind === "courses" ? null : route.courseId
  const selectedLessonId = route.kind === "chat" ? route.lessonId : null
  const selectedLessonVersion = route.kind === "chat" ? route.lessonVersion : null
  const activeSessionId = route.kind === "chat" ? route.sessionId : null

  useEffect(() => {
    let active = true

    async function loadCourses() {
      setCoursesLoading(true)

      try {
        const result = await courseApi.listDiscoverable()

        if (active) {
          setCourses(result.courses)
        }
      } catch {
        if (active) {
          setCourses([])
        }
      } finally {
        if (active) {
          setCoursesLoading(false)
        }
      }
    }

    void loadCourses()

    return () => {
      active = false
    }
  }, [courseApi])

  useEffect(() => {
    let active = true

    async function loadLessons() {
      if (!selectedCourseId) {
        setLessons([])
        setLessonsLoading(false)
        return
      }

      setLessonsLoading(true)

      try {
        const result = await courseApi.listLessons(selectedCourseId)

        if (active) {
          setLessons(result.lessons)
        }
      } catch {
        if (active) {
          setLessons([])
        }
      } finally {
        if (active) {
          setLessonsLoading(false)
        }
      }
    }

    void loadLessons()

    return () => {
      active = false
    }
  }, [courseApi, selectedCourseId])

  useEffect(() => {
    let active = true

    async function loadSessions() {
      if (!selectedCourseId || !selectedLessonId || !selectedLessonVersion) {
        setSessions([])
        setSessionsError(null)
        setSessionsLoading(false)
        return
      }

      setSessionsLoading(true)
      setSessionsError(null)

      try {
        const result = await sessionApi.listSessions(
          selectedCourseId,
          selectedLessonId,
          selectedLessonVersion,
        )

        if (active) {
          setSessions(sortSessionsByUpdatedAt(result.sessions))
        }
      } catch {
        if (active) {
          setSessions([])
          setSessionsError("Unable to load prior sessions for this lesson.")
        }
      } finally {
        if (active) {
          setSessionsLoading(false)
        }
      }
    }

    void loadSessions()

    return () => {
      active = false
    }
  }, [
    selectedCourseId,
    selectedLessonId,
    selectedLessonVersion,
    sessionApi,
  ])

  useEffect(() => {
    const element = railScrollRef.current
    const pending = pendingPrependCompensationRef.current
    if (!element || pending === null) {
      return
    }

    const delta = element.scrollHeight - pending.previousScrollHeight
    element.scrollTop = pending.previousScrollTop + delta
    pendingPrependCompensationRef.current = null
  }, [sessions.length])

  useEffect(() => {
    function handleSessionChange(event: Event) {
      const detail = (event as CustomEvent<{
        courseId: string
        lessonId: string
        lessonVersion: string
        change:
          | { type: "upsert"; session: Session }
          | { type: "delete"; sessionId: string }
      }>).detail

      if (
        !detail ||
        detail.courseId !== selectedCourseId ||
        detail.lessonId !== selectedLessonId ||
        detail.lessonVersion !== selectedLessonVersion
      ) {
        return
      }

      const change = detail.change

      if (change.type === "delete") {
        setSessions((current) =>
          current.filter((session) => session.session_id !== change.sessionId),
        )
        return
      }

      setSessions((current) => {
        const existingIndex = current.findIndex(
          (session) => session.session_id === change.session.session_id,
        )

        if (existingIndex === -1) {
          const element = railScrollRef.current
          if (element) {
            pendingPrependCompensationRef.current = {
              previousScrollHeight: element.scrollHeight,
              previousScrollTop: element.scrollTop,
            }
          }
          return sortSessionsByUpdatedAt([change.session, ...current])
        }

        return sortSessionsByUpdatedAt(
          current.map((session) =>
            session.session_id === change.session.session_id
              ? change.session
              : session,
          ),
        )
      })
    }

    window.addEventListener("plexa:sessions-changed", handleSessionChange as EventListener)
    return () => {
      window.removeEventListener("plexa:sessions-changed", handleSessionChange as EventListener)
    }
  }, [selectedCourseId, selectedLessonId, selectedLessonVersion])

  const selectedCourse = useMemo(
    () => courses.find((course) => course.course_id === selectedCourseId) ?? null,
    [courses, selectedCourseId],
  )

  const selectedLesson = useMemo(
    () =>
      lessons.find(
        (lesson) =>
          lesson.lesson_id === selectedLessonId &&
          lesson.version === selectedLessonVersion,
      ) ?? null,
    [lessons, selectedLessonId, selectedLessonVersion],
  )
  const visibleCourses = useMemo(
    () =>
      visibleRailItems(
        courses,
        coursesExpanded,
        (course) => course.course_id === selectedCourseId,
      ),
    [courses, coursesExpanded, selectedCourseId],
  )
  const visibleLessons = useMemo(
    () =>
      visibleRailItems(
        lessons,
        lessonsExpanded,
        (lesson) =>
          lesson.lesson_id === selectedLessonId &&
          lesson.version === selectedLessonVersion,
      ),
    [lessons, lessonsExpanded, selectedLessonId, selectedLessonVersion],
  )
  const visibleSessions = useMemo(
    () =>
      visibleRailItems(
        sessions,
        sessionsExpanded,
        (session) => session.session_id === activeSessionId,
      ),
    [activeSessionId, sessions, sessionsExpanded],
  )


  function handleSessionCardKeyDown(
    event: KeyboardEvent<HTMLElement>,
    session: Session,
  ) {
    if (event.key !== "Enter" && event.key !== " ") {
      return
    }

    event.preventDefault()
    navigate(
      `/app/courses/${encodeURIComponent(session.course_id)}/lessons/${encodeURIComponent(session.lesson_id)}/${encodeURIComponent(session.lesson_version)}/sessions/${encodeURIComponent(session.session_id)}`,
    )
  }

  async function handleConfirmDeleteSession() {
    if (sessionPendingDelete === null) {
      return
    }

    setSessionDeleting(true)

    try {
      await sessionApi.deleteSession(
        sessionPendingDelete.course_id,
        sessionPendingDelete.lesson_id,
        sessionPendingDelete.lesson_version,
        sessionPendingDelete.session_id,
      )

      const deletedActiveSession = sessionPendingDelete.session_id === activeSessionId

      setSessionPendingDelete(null)
      setSessions((current) =>
        current.filter((session) => session.session_id !== sessionPendingDelete.session_id),
      )

      if (deletedActiveSession) {
        navigate(
          `/app/courses/${encodeURIComponent(sessionPendingDelete.course_id)}/lessons/${encodeURIComponent(sessionPendingDelete.lesson_id)}/${encodeURIComponent(sessionPendingDelete.lesson_version)}`,
        )
      }
    } catch {
      setSessionsError("Unable to delete this session right now.")
    } finally {
      setSessionDeleting(false)
    }
  }

  async function handleCreateSession() {
    if (!selectedCourseId || !selectedLesson || sessionCreating) {
      return
    }

    setSessionCreating(true)
    setSessionsError(null)

    try {
      const result = await sessionApi.createSession(
        selectedCourseId,
        selectedLesson.lesson_id,
        selectedLesson.version,
      )
      const element = railScrollRef.current
      if (element) {
        pendingPrependCompensationRef.current = {
          previousScrollHeight: element.scrollHeight,
          previousScrollTop: element.scrollTop,
        }
      }
      setSessions((current) => sortSessionsByUpdatedAt([result.session, ...current]))
      navigate(
        `/app/courses/${encodeURIComponent(selectedCourseId)}/lessons/${encodeURIComponent(selectedLesson.lesson_id)}/${encodeURIComponent(selectedLesson.version)}/sessions/${encodeURIComponent(result.session.session_id)}`,
      )
    } catch {
      setSessionsError("Unable to start a new session right now.")
    } finally {
      setSessionCreating(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className="app-shell__rail">
        <div className="rail__brand">
          <div>
            <p className="eyebrow">Student Workspace</p>
            <h1>Plexa</h1>
          </div>
          <div className="rail__brand-actions">
            <button className="ghost-button" onClick={toggleTheme}>
              {theme === "light" ? "Dark mode" : "Light mode"}
            </button>
            <button
              className="ghost-button"
              onClick={() => {
                void onLogout().then(() => {
                  navigate("/login", { replace: true })
                })
              }}
            >
              Logout
            </button>
          </div>
        </div>

        <div
          ref={railScrollRef}
          className="rail__scroll"
        >
          <section className="rail__section">
            <div className="rail__section-header">
              <h2>Courses</h2>
              <button
                className="ghost-button"
                onClick={() => navigate("/app/courses")}
              >
                Browse
              </button>
            </div>

            <div className="rail__list">
              {coursesLoading ? <div className="empty-panel">Loading courses...</div> : null}

              {!coursesLoading &&
                visibleCourses.map((course) => {
                  const isActive = course.course_id === selectedCourseId

                  return (
                    <button
                      key={course.course_id}
                      className={isActive ? "rail-card rail-card--active" : "rail-card"}
                      onClick={() =>
                        navigate(`/app/courses/${encodeURIComponent(course.course_id)}`)
                      }
                    >
                      <span className="rail-card__title">{course.title}</span>
                      {course.description ? (
                        <span className="rail-card__meta">{course.description}</span>
                      ) : null}
                    </button>
                  )
                })}
              {!coursesLoading && courses.length > 4 ? (
                <button
                  className="ghost-button rail__toggle"
                  onClick={() => setCoursesExpanded((current) => !current)}
                >
                  {coursesExpanded ? "Show Less" : "Show More"}
                </button>
              ) : null}
            </div>
          </section>

          <section className="rail__section">
            <div className="rail__section-header">
              <h2>Lessons</h2>
              {selectedCourse ? (
                <span className="section-chip">{selectedCourse.course_id}</span>
              ) : null}
            </div>

            {selectedCourseId ? (
              <div className="rail__list">
                {lessonsLoading ? <div className="empty-panel">Loading lessons...</div> : null}

                {!lessonsLoading &&
                  visibleLessons.map((lesson) => {
                    const isActive =
                      lesson.lesson_id === selectedLessonId &&
                      lesson.version === selectedLessonVersion

                    return (
                      <button
                        key={`${lesson.lesson_id}:${lesson.version}`}
                        className={
                          [
                            "rail-card",
                            isActive ? "rail-card--active" : "",
                            lesson.is_pinned_now ? "rail-card--pinned" : "",
                          ]
                            .filter(Boolean)
                            .join(" ")
                        }
                        onClick={() =>
                          navigate(
                            `/app/courses/${encodeURIComponent(selectedCourseId)}/lessons/${encodeURIComponent(lesson.lesson_id)}/${encodeURIComponent(lesson.version)}`,
                          )
                        }
                      >
                        <span className="rail-card__title rail-card__title--with-icon">
                          {lesson.is_pinned_now ? (
                            <span className="pin-indicator" aria-label="Pinned lesson" title="Pinned lesson">
                              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                                <path d="M15 3c.55 0 1 .45 1 1v2.17l2.41 2.42c.38.37.59.88.59 1.41V12c0 .55-.45 1-1 1h-5v7l-1 1-1-1v-7H6c-.55 0-1-.45-1-1V10c0-.53.21-1.04.59-1.41L8 6.17V4c0-.55.45-1 1-1h6Z" fill="currentColor" />
                              </svg>
                            </span>
                          ) : null}
                          <span>{lesson.title}</span>
                        </span>
                        <span className="rail-card__meta">
                          {lesson.difficulty ?? "Open level"}
                        </span>
                      </button>
                    )
                  })}
                {!lessonsLoading && lessons.length > 4 ? (
                  <button
                    className="ghost-button rail__toggle"
                    onClick={() => setLessonsExpanded((current) => !current)}
                  >
                    {lessonsExpanded ? "Show Less" : "Show More"}
                  </button>
                ) : null}
              </div>
            ) : (
              <div className="empty-panel">
                Choose a course to view lesson options.
              </div>
            )}
          </section>

          <section className="rail__section rail__section--flex">
            <div className="rail__section-header">
              <h2>Sessions</h2>
              {selectedLesson ? (
                <button
                  className="ghost-button"
                  onClick={() => void handleCreateSession()}
                  disabled={sessionCreating}
                >
                  {sessionCreating ? "Starting..." : "New"}
                </button>
              ) : null}
            </div>

            {!selectedLesson ? (
              <div className="empty-panel">
                Select a lesson to view prior sessions.
              </div>
            ) : (
              <div className="rail__list">
                {sessionsLoading ? <div className="empty-panel">Loading session history...</div> : null}

                {!sessionsLoading && sessionsError ? (
                  <div className="empty-panel">{sessionsError}</div>
                ) : null}

                {!sessionsLoading && !sessionsError && sessions.length === 0 ? (
                  <div className="empty-panel">
                    No prior sessions yet.
                  </div>
                ) : null}

                {!sessionsLoading &&
                  !sessionsError &&
                  visibleSessions.map((session) => {
                    const isActive = session.session_id === activeSessionId

                    return (
                      <article
                        key={session.session_id}
                        className={isActive ? "session-card session-card--active session-card--deletable" : "session-card session-card--deletable"}
                      >
                        <div
                          className="session-card__main"
                          role="button"
                          tabIndex={0}
                          onClick={() =>
                            navigate(
                              `/app/courses/${encodeURIComponent(session.course_id)}/lessons/${encodeURIComponent(session.lesson_id)}/${encodeURIComponent(session.lesson_version)}/sessions/${encodeURIComponent(session.session_id)}`,
                            )
                          }
                          onKeyDown={(event) => handleSessionCardKeyDown(event, session)}
                        >
                          <span className="session-card__title">
                            {session.title}
                          </span>
                          <span className="session-card__meta">
                            {session.is_active ? "Open session" : "Closed session"} ·{" "}
                            {formatSessionTimestamp(session.updated_at)}
                          </span>
                          <span className="session-card__meta">
                            {session.turn_count} / {session.max_turns} turns
                          </span>
                        </div>
                        <button
                          className="session-card__delete"
                          type="button"
                          aria-label="Delete session"
                          onClick={(event) => {
                            event.stopPropagation()
                            setSessionPendingDelete(session)
                          }}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                            <path d="M9 3h6l1 2h4v2H4V5h4l1-2Zm1 7h2v7h-2v-7Zm4 0h2v7h-2v-7ZM7 10h2v7H7v-7Zm1 10h8a2 2 0 0 0 2-2V8H6v10a2 2 0 0 0 2 2Z" fill="currentColor" />
                          </svg>
                        </button>
                      </article>
                    )
                  })}
                {!sessionsLoading && !sessionsError && sessions.length > 4 ? (
                  <button
                    className="ghost-button rail__toggle"
                    onClick={() => setSessionsExpanded((current) => !current)}
                  >
                    {sessionsExpanded ? "Show Less" : "Show More"}
                  </button>
                ) : null}
              </div>
            )}
          </section>
        </div>
      </aside>

      <section className="app-shell__main">
        <header className="workspace-header">
          <div>
            <h2>
              {selectedLesson?.title ??
                selectedCourse?.title ??
                "Course and lesson selection"}
            </h2>
          </div>

          <div className="workspace-header__meta">
            <span className="section-chip">{userId ?? "Unknown user"}</span>
            {selectedCourse ? (
              <span className="section-chip">{selectedCourse.course_id}</span>
            ) : null}
            {selectedLesson ? (
              <>
                <span className="section-chip">v{selectedLesson.version}</span>
                <span className="section-chip">
                  {activeSessionId ? "Session selected" : "Ready for new session"}
                </span>
              </>
            ) : null}
          </div>
        </header>

        <main className="workspace-main">{children}</main>
      </section>

      {sessionPendingDelete ? (
        <aside className="modal-backdrop" aria-hidden="true">
          <section
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-session-rail-title"
          >
            <p className="eyebrow">Confirm Action</p>
            <h2 id="delete-session-rail-title">Delete this session?</h2>
            <p>
              This permanently removes the selected session from this lesson history.
            </p>
            <footer className="modal-actions">
              <button
                className="ghost-button"
                onClick={() => setSessionPendingDelete(null)}
                disabled={sessionDeleting}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                onClick={() => void handleConfirmDeleteSession()}
                disabled={sessionDeleting}
              >
                {sessionDeleting ? "Deleting..." : "Delete session"}
              </button>
            </footer>
          </section>
        </aside>
      ) : null}

      <aside className="app-shell__context">
        <section className="context-panel">
          <header className="context-panel__header">
            <p className="eyebrow">Lesson Context</p>
          </header>
          {selectedLesson ? (
            <>
              <h3>{selectedLesson.title}</h3>
              <dl className="context-list">
                <div>
                  <dt>Author</dt>
                  <dd>{selectedLesson.author ?? "Unknown"}</dd>
                </div>
                <div>
                  <dt>Difficulty</dt>
                  <dd>{selectedLesson.difficulty ?? "Not specified"}</dd>
                </div>
                <div>
                  <dt>Approx. Time</dt>
                  <dd>{selectedLesson.approximate_time ?? "Flexible"}</dd>
                </div>
                <div>
                  <dt>Objective</dt>
                  <dd>{selectedLesson.learning_objective ?? "Objective unavailable"}</dd>
                </div>
                <div>
                  <dt>Behavioral Focus</dt>
                  <dd>{selectedLesson.behavioral_focus ?? "Not specified"}</dd>
                </div>
              </dl>

              {selectedLesson.tags?.length ? (
                <div className="tag-row">
                  {selectedLesson.tags.map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <>
              <h3>Context will live here</h3>
              <p>
                Select a lesson to keep its goals, framing, and constraints visible
                while you work through multiple chat sessions.
              </p>
            </>
          )}
        </section>
      </aside>
    </div>
  )
}
