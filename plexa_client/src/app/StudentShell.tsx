import { useEffect, useMemo, useState, type KeyboardEvent, type ReactNode } from "react"
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

export default function StudentShell({
  route,
  userId,
  onLogout,
  children,
}: StudentShellProps) {
  const { courseApi, sessionApi } = useApis()
  const { theme, toggleTheme } = useTheme()
  const [courses, setCourses] = useState<Course[]>([])
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [lessonsLoading, setLessonsLoading] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [sessionRefreshKey, setSessionRefreshKey] = useState(0)
  const [sessionPendingDelete, setSessionPendingDelete] = useState<Session | null>(null)
  const [sessionDeleting, setSessionDeleting] = useState(false)
  const [sessionCreating, setSessionCreating] = useState(false)

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
          setSessions(result.sessions)
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
    activeSessionId,
    selectedCourseId,
    selectedLessonId,
    selectedLessonVersion,
    sessionApi,
    sessionRefreshKey,
  ])

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
      setSessionRefreshKey((value) => value + 1)

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
      setSessionRefreshKey((value) => value + 1)
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

        <div className="rail__scroll">
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
                courses.map((course) => {
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
                  lessons.map((lesson) => {
                    const isActive =
                      lesson.lesson_id === selectedLessonId &&
                      lesson.version === selectedLessonVersion

                    return (
                      <button
                        key={`${lesson.lesson_id}:${lesson.version}`}
                        className={isActive ? "rail-card rail-card--active" : "rail-card"}
                        onClick={() =>
                          navigate(
                            `/app/courses/${encodeURIComponent(selectedCourseId)}/lessons/${encodeURIComponent(lesson.lesson_id)}/${encodeURIComponent(lesson.version)}`,
                          )
                        }
                      >
                        <span className="rail-card__title">{lesson.title}</span>
                        <span className="rail-card__meta">
                          {lesson.difficulty ?? "Open level"}
                        </span>
                      </button>
                    )
                  })}
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
                  sessions.map((session) => {
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
                            {session.is_active ? "Open session" : "Closed session"}
                          </span>
                          <span className="session-card__meta">
                            {formatSessionTimestamp(session.created_at)}
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
