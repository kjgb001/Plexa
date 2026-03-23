import { useEffect, useMemo, useState, type ReactNode } from "react"
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
                onClick={() =>
                  navigate(
                    `/app/courses/${encodeURIComponent(selectedCourseId ?? "")}/lessons/${encodeURIComponent(selectedLesson.lesson_id)}/${encodeURIComponent(selectedLesson.version)}`,
                  )
                }
              >
                New
              </button>
            ) : null}
          </div>

          {!selectedLesson ? (
            <div className="empty-panel">
              Select a lesson to see prior sessions and start a new one.
            </div>
          ) : (
            <div className="rail__list">
              <button
                className={
                  activeSessionId === null ? "session-card session-card--active" : "session-card"
                }
                onClick={() =>
                  navigate(
                    `/app/courses/${encodeURIComponent(selectedCourseId ?? "")}/lessons/${encodeURIComponent(selectedLesson.lesson_id)}/${encodeURIComponent(selectedLesson.version)}`,
                  )
                }
              >
                <span className="session-card__title">New session</span>
                <span className="session-card__meta">
                  Start a fresh conversation for this lesson.
                </span>
              </button>

              {sessionsLoading ? <div className="empty-panel">Loading session history...</div> : null}

              {!sessionsLoading && sessionsError ? (
                <div className="empty-panel">{sessionsError}</div>
              ) : null}

              {!sessionsLoading && !sessionsError && sessions.length === 0 ? (
                <div className="empty-panel">
                  No prior sessions yet. Start a new one when you are ready.
                </div>
              ) : null}

              {!sessionsLoading &&
                !sessionsError &&
                sessions.map((session) => {
                  const isActive = session.session_id === activeSessionId

                  return (
                    <button
                      key={session.session_id}
                      className={isActive ? "session-card session-card--active" : "session-card"}
                      onClick={() =>
                        navigate(
                          `/app/courses/${encodeURIComponent(session.course_id)}/lessons/${encodeURIComponent(session.lesson_id)}/${encodeURIComponent(session.lesson_version)}/sessions/${encodeURIComponent(session.session_id)}`,
                        )
                      }
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
                    </button>
                  )
                })}
            </div>
          )}
        </section>
      </aside>

      <div className="app-shell__main">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Active Context</p>
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
      </div>

      <aside className="app-shell__context">
        <div className="context-card">
          <p className="eyebrow">Lesson Context</p>
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
        </div>
      </aside>
    </div>
  )
}
