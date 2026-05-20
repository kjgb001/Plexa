import { useEffect, useMemo, useState } from "react"
import { useApis } from "../../api"
import { ApiError, NotFoundError } from "../../api/errors"
import type { Course, CourseInstructors, EncryptedLogMetadata, Lesson } from "../../api/interfaces"

export function InstructorCourseScreen({
  courseId,
}: {
  courseId: string
}) {
  const { instructorApi } = useApis()
  const [course, setCourse] = useState<Course | null>(null)
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [instructors, setInstructors] = useState<CourseInstructors | null>(null)
  const [pendingRequests, setPendingRequests] = useState<string[]>([])
  const [logs, setLogs] = useState<EncryptedLogMetadata[]>([])
  const [selectedLog, setSelectedLog] = useState<Record<string, unknown> | null>(null)
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [addInstructorUserId, setAddInstructorUserId] = useState("")
  const [mutating, setMutating] = useState(false)

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setLoadError(null)

      try {
        const [courseResult, lessonsResult, instructorsResult, logsResult] = await Promise.all([
          instructorApi.getCourse(courseId),
          instructorApi.listLessons(courseId),
          instructorApi.listInstructors(courseId),
          instructorApi.listLogs(courseId),
        ])

        let requests: string[] = []
        try {
          const requestResult = await instructorApi.listRequests(courseId)
          requests = requestResult.pending_requests
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 404) {
            throw error
          }
        }

        if (!active) {
          return
        }

        setCourse(courseResult)
        setLessons(lessonsResult)
        setInstructors(instructorsResult)
        setPendingRequests(requests)
        setLogs(logsResult)
      } catch (error) {
        if (!active) {
          return
        }

        console.error("Failed to load instructor course workspace", error)
        if (error instanceof NotFoundError) {
          setLoadError("This course is not available to your instructor account.")
        } else {
          setLoadError("Failed to load course workspace.")
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      active = false
    }
  }, [courseId, instructorApi])

  const pinnedLesson = useMemo(
    () => lessons.find((lesson) => lesson.is_pinned_now) ?? null,
    [lessons],
  )

  async function handleAddInstructor() {
    if (!addInstructorUserId.trim()) {
      return
    }

    setMutating(true)
    try {
      const next = await instructorApi.addInstructor(courseId, addInstructorUserId.trim())
      setInstructors(next)
      setAddInstructorUserId("")
    } finally {
      setMutating(false)
    }
  }

  async function handleRemoveInstructor(userId: string) {
    setMutating(true)
    try {
      const next = await instructorApi.removeInstructor(courseId, userId)
      setInstructors(next)
    } finally {
      setMutating(false)
    }
  }

  async function handleApproveRequest(userId: string) {
    setMutating(true)
    try {
      await instructorApi.approveRequest(courseId, userId)
      setPendingRequests((current) => current.filter((value) => value !== userId))
    } finally {
      setMutating(false)
    }
  }

  async function handleRemoveStudent(userId: string) {
    setMutating(true)
    try {
      await instructorApi.removeStudent(courseId, userId)
      setCourse((current) =>
        current
          ? { ...current, enrolled_users: current.enrolled_users.filter((value) => value !== userId) }
          : current,
      )
    } finally {
      setMutating(false)
    }
  }

  async function handleOpenLog(sessionId: string) {
    setSelectedLogId(sessionId)
    const payload = await instructorApi.getLog(courseId, sessionId)
    setSelectedLog(payload)
  }

  if (loading) {
    return (
      <section className="portal-stage">
        <header className="portal-stage__hero">
          <p className="eyebrow">Instructor Workspace</p>
          <h1>Loading course workspace</h1>
        </header>
      </section>
    )
  }

  if (loadError || course === null || instructors === null) {
    return (
      <section className="portal-stage">
        <header className="portal-stage__hero">
          <p className="eyebrow">Instructor Workspace</p>
          <h1>Course unavailable</h1>
          <p className="portal-stage__summary">{loadError ?? "Unable to load this course."}</p>
        </header>
      </section>
    )
  }

  return (
    <section className="portal-stage" aria-labelledby="instructor-course-title">
      <header className="portal-stage__hero">
        <p className="eyebrow">Instructor Workspace</p>
        <h1 id="instructor-course-title">{course.title}</h1>
        <p className="portal-stage__summary">
          The instructor portal is now a separate surface sharing the same auth, API, and theme layer
          as the student portal. This first slice focuses on course oversight and control.
        </p>
      </header>

      <section className="portal-grid portal-grid--wide">
        <article className="portal-card">
          <header className="portal-card__header">
            <h2>Course overview</h2>
            <span className="section-chip">{course.course_id}</span>
          </header>
          <dl className="context-list">
            <div>
              <dt>Owner</dt>
              <dd>{instructors.owner_id}</dd>
            </div>
            <div>
              <dt>Enrolled</dt>
              <dd>{course.enrolled_users.length}</dd>
            </div>
            <div>
              <dt>Pending</dt>
              <dd>{pendingRequests.length}</dd>
            </div>
            <div>
              <dt>Current lesson</dt>
              <dd>{pinnedLesson ? `${pinnedLesson.title} (${pinnedLesson.version})` : "No pinned lesson"}</dd>
            </div>
          </dl>
        </article>

        <article className="portal-card">
          <header className="portal-card__header">
            <h2>Lesson timeline</h2>
          </header>
          <p className="portal-note">
            Timeline editing is not wired in yet on the server API. This portal slice shows the current pinned lesson
            state so the later scheduler UI can land on top of the same course model.
          </p>
          <div className="portal-list">
            {lessons.map((lesson) => (
              <div
                key={`${lesson.lesson_id}:${lesson.version}`}
                className={lesson.is_pinned_now ? "portal-list__item portal-list__item--active" : "portal-list__item"}
              >
                <span className="portal-list__title">{lesson.title}</span>
                <span className="portal-list__meta">
                  {lesson.is_pinned_now ? "Pinned now" : `v${lesson.version}`}
                </span>
              </div>
            ))}
          </div>
        </article>

        <article className="portal-card">
          <header className="portal-card__header">
            <h2>Instructor roster</h2>
          </header>
          <div className="portal-inline-form">
            <input
              value={addInstructorUserId}
              onChange={(event) => setAddInstructorUserId(event.target.value)}
              placeholder="assistant-1"
            />
            <button className="primary-button" disabled={mutating} onClick={() => void handleAddInstructor()}>
              Add instructor
            </button>
          </div>
          <div className="portal-list">
            {instructors.instructor_ids.map((userId) => (
              <div key={userId} className="portal-list__item portal-list__item--split">
                <span className="portal-list__title">{userId}</span>
                {userId !== instructors.owner_id ? (
                  <button className="ghost-button" disabled={mutating} onClick={() => void handleRemoveInstructor(userId)}>
                    Remove
                  </button>
                ) : (
                  <span className="section-chip">Owner</span>
                )}
              </div>
            ))}
          </div>
        </article>

        <article className="portal-card">
          <header className="portal-card__header">
            <h2>Learner requests and roster</h2>
          </header>
          <div className="portal-list">
            {pendingRequests.map((userId) => (
              <div key={`pending:${userId}`} className="portal-list__item portal-list__item--split">
                <span className="portal-list__title">{userId}</span>
                <button className="primary-button" disabled={mutating} onClick={() => void handleApproveRequest(userId)}>
                  Approve
                </button>
              </div>
            ))}
            {course.enrolled_users.map((userId) => (
              <div key={`enrolled:${userId}`} className="portal-list__item portal-list__item--split">
                <span className="portal-list__title">{userId}</span>
                <button className="ghost-button" disabled={mutating} onClick={() => void handleRemoveStudent(userId)}>
                  Remove
                </button>
              </div>
            ))}
            {pendingRequests.length === 0 && course.enrolled_users.length === 0 ? (
              <p className="empty-panel">No roster activity yet.</p>
            ) : null}
          </div>
        </article>

        <article className="portal-card portal-card--span-2">
          <header className="portal-card__header">
            <h2>Encrypted session logs</h2>
          </header>
          <div className="portal-log-grid">
            <div className="portal-list">
              {logs.map((log) => (
                <button
                  key={log.instance_id}
                  className={selectedLogId === log.instance_id ? "portal-list__item portal-list__item--active" : "portal-list__item"}
                  onClick={() => void handleOpenLog(log.instance_id)}
                >
                  <span className="portal-list__title">{log.user_id}</span>
                  <span className="portal-list__meta">
                    {log.lesson_id} · {log.turn_count} turns
                  </span>
                </button>
              ))}
              {logs.length === 0 ? <p className="empty-panel">No encrypted logs available yet.</p> : null}
            </div>
            <div className="portal-log-preview">
              {selectedLog ? (
                <pre>{JSON.stringify(selectedLog, null, 2)}</pre>
              ) : (
                <p className="empty-panel">Select a log to inspect its decrypted session payload.</p>
              )}
            </div>
          </div>
        </article>
      </section>
    </section>
  )
}
