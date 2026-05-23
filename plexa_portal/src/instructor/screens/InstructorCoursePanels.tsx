import { useEffect, useMemo, useState } from "react"
import type { Course, CourseInstructors, CourseLessonWindow, EncryptedLogMetadata, Lesson } from "../../api/interfaces"

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Unavailable"
  }
  return new Date(value).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function toDatetimeLocal(value: string | null | undefined): string {
  if (!value) {
    return ""
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ""
  }
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return localDate.toISOString().slice(0, 16)
}

function fromDatetimeLocal(value: string): string {
  return new Date(value).toISOString()
}

function formatDatetimeLocal(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  const hours = String(date.getHours()).padStart(2, "0")
  const minutes = String(date.getMinutes()).padStart(2, "0")
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

function getTomorrowMidnight(): Date {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(0, 0, 0, 0)
  return tomorrow
}

function getDefaultTimelineWindowDates(): Pick<TimelineDraftWindow, "starts_at" | "ends_at"> {
  const startsAt = getTomorrowMidnight()
  return {
    starts_at: formatDatetimeLocal(startsAt),
    ends_at: formatDatetimeLocal(addDays(startsAt, 1)),
  }
}

interface TimelineDraftWindow {
  lesson_id: string
  lesson_version: string
  starts_at: string
  ends_at: string
}

export function InstructorOverviewPanel({
  course,
  instructors,
  pendingRequests,
  lessons,
  logs,
}: {
  course: Course
  instructors: CourseInstructors
  pendingRequests: string[]
  lessons: Lesson[]
  logs: EncryptedLogMetadata[]
}) {
  const pinnedLesson = useMemo(
    () => lessons.find((lesson) => lesson.is_pinned_now) ?? null,
    [lessons],
  )
  const recentLog = useMemo(
    () => [...logs].sort((left, right) => right.last_event_at.localeCompare(left.last_event_at))[0] ?? null,
    [logs],
  )

  return (
    <section className="portal-grid portal-grid--wide">
      <article className="portal-card">
        <header className="portal-card__header">
          <h2>Course overview</h2>
          <span className="section-chip">{course.course_id}</span>
        </header>
        <dl className="context-list">
          <div><dt>Owner</dt><dd>{instructors.owner_id}</dd></div>
          <div><dt>Instructors</dt><dd>{instructors.instructor_ids.length}</dd></div>
          <div><dt>Enrolled learners</dt><dd>{course.enrolled_users.length}</dd></div>
          <div><dt>Pending requests</dt><dd>{pendingRequests.length}</dd></div>
          <div><dt>Bound lessons</dt><dd>{lessons.length}</dd></div>
        </dl>
      </article>

      <article className="portal-card">
        <header className="portal-card__header">
          <h2>Current lesson state</h2>
        </header>
        <dl className="context-list">
          <div>
            <dt>Pinned lesson</dt>
            <dd>{pinnedLesson ? `${pinnedLesson.title} (${pinnedLesson.version})` : "No pinned lesson"}</dd>
          </div>
          <div>
            <dt>Recent log activity</dt>
            <dd>{recentLog ? formatTimestamp(recentLog.last_event_at) : "No session activity yet"}</dd>
          </div>
          <div>
            <dt>Latest actor</dt>
            <dd>{recentLog?.user_id ?? "Unavailable"}</dd>
          </div>
        </dl>
      </article>

      <article className="portal-card portal-card--span-2">
        <header className="portal-card__header">
          <h2>Instructor focus</h2>
        </header>
        <p className="portal-note">
          Use the course modes to move between lesson sequencing, builder work, session review, analytics, and roster management.
        </p>
      </article>
    </section>
  )
}

export function InstructorLessonsPanel({
  course,
  lessons,
  mutating,
  onUpdateTimeline,
}: {
  course: Course
  lessons: Lesson[]
  mutating: boolean
  onUpdateTimeline(lessonTimeline: CourseLessonWindow[]): Promise<void>
}) {
  const [draftTimeline, setDraftTimeline] = useState<TimelineDraftWindow[]>([])
  const [timelineError, setTimelineError] = useState<string | null>(null)
  const lessonOptions = useMemo(
    () => lessons.map((lesson) => ({
      key: `${lesson.lesson_id}:${lesson.version}`,
      label: `${lesson.title} (${lesson.version})`,
    })),
    [lessons],
  )
  const pinnedLesson = useMemo(
    () => lessons.find((lesson) => lesson.is_pinned_now) ?? null,
    [lessons],
  )

  useEffect(() => {
    setDraftTimeline(course.lesson_timeline.map((window) => ({
      lesson_id: window.lesson_id,
      lesson_version: window.lesson_version,
      starts_at: toDatetimeLocal(window.starts_at),
      ends_at: toDatetimeLocal(window.ends_at),
    })))
    setTimelineError(null)
  }, [course.lesson_timeline])

  function addWindow() {
    const firstLesson = lessons[0]
    if (!firstLesson) {
      return
    }
    const defaultDates = getDefaultTimelineWindowDates()
    setDraftTimeline((current) => [
      ...current,
      {
        lesson_id: firstLesson.lesson_id,
        lesson_version: firstLesson.version,
        ...defaultDates,
      },
    ])
  }

  function updateWindow(index: number, patch: Partial<TimelineDraftWindow>) {
    setDraftTimeline((current) =>
      current.map((window, windowIndex) => windowIndex === index ? { ...window, ...patch } : window),
    )
  }

  function updateWindowLesson(index: number, lessonKey: string) {
    const selected = lessons.find((lesson) => `${lesson.lesson_id}:${lesson.version}` === lessonKey)
    if (!selected) {
      return
    }
    updateWindow(index, {
      lesson_id: selected.lesson_id,
      lesson_version: selected.version,
    })
  }

  function removeWindow(index: number) {
    setDraftTimeline((current) => current.filter((_, windowIndex) => windowIndex !== index))
  }

  function buildTimelinePayload(source: TimelineDraftWindow[]): CourseLessonWindow[] | null {
    if (source.some((window) => !window.lesson_id || !window.lesson_version || !window.starts_at)) {
      setTimelineError("Every timeline window needs a lesson and start time.")
      return null
    }
    const payload = source.map((window) => ({
      lesson_id: window.lesson_id,
      lesson_version: window.lesson_version,
      starts_at: fromDatetimeLocal(window.starts_at),
      ends_at: window.ends_at ? fromDatetimeLocal(window.ends_at) : null,
    }))
    if (payload.some((window) => window.ends_at !== null && window.ends_at <= window.starts_at)) {
      setTimelineError("Timeline windows must end after they start.")
      return null
    }
    setTimelineError(null)
    return payload
  }

  async function saveTimeline() {
    const payload = buildTimelinePayload(draftTimeline)
    if (payload === null) {
      return
    }
    try {
      await onUpdateTimeline(payload)
    } catch (error) {
      console.error("Failed to update lesson timeline", error)
      setTimelineError("Failed to save timeline.")
    }
  }

  async function pinNow(lesson: Lesson) {
    const now = new Date()
    const nowMs = now.getTime()
    const preservedWindows = course.lesson_timeline
      .filter((window) => {
        const startsAt = new Date(window.starts_at).getTime()
        const endsAt = window.ends_at ? new Date(window.ends_at).getTime() : null
        return (endsAt !== null && endsAt <= nowMs) || startsAt > nowMs
      })
      .sort((left, right) => new Date(left.starts_at).getTime() - new Date(right.starts_at).getTime())
    const nextFutureWindow = preservedWindows.find((window) => new Date(window.starts_at).getTime() > nowMs)
    const currentWindow = {
      lesson_id: lesson.lesson_id,
      lesson_version: lesson.version,
      starts_at: now.toISOString(),
      ends_at: nextFutureWindow?.starts_at ?? null,
    }
    const pastWindows = preservedWindows.filter((window) => {
      const endsAt = window.ends_at ? new Date(window.ends_at).getTime() : null
      return endsAt !== null && endsAt <= nowMs
    })
    const futureWindows = preservedWindows.filter((window) => new Date(window.starts_at).getTime() > nowMs)
    const payload = [...pastWindows, currentWindow, ...futureWindows]
    setTimelineError(null)
    try {
      await onUpdateTimeline(payload)
    } catch (error) {
      console.error("Failed to pin lesson", error)
      setTimelineError("Failed to pin lesson.")
    }
  }

  return (
    <section className="portal-grid portal-grid--wide">
      <article className="portal-card portal-card--span-2">
        <header className="portal-card__header">
          <h2>Lessons in course</h2>
          <span className="section-chip">
            {pinnedLesson ? `Pinned: ${pinnedLesson.title}` : "No pinned lesson"}
          </span>
        </header>
        <p className="portal-note">
          Schedule lesson windows to control the pinned lesson state learners see in the course sidebar.
        </p>
        <div className="portal-list">
          {lessons.map((lesson) => (
            <div
              key={`${lesson.lesson_id}:${lesson.version}`}
              className={lesson.is_pinned_now ? "portal-list__item portal-list__item--active" : "portal-list__item"}
            >
              <span className="portal-list__title">{lesson.title}</span>
              <span className="portal-list__meta">
                {lesson.is_pinned_now ? "Pinned now" : `v${lesson.version}`} · {lesson.learning_objective ?? "No objective summary"}
              </span>
              <div className="portal-inline-actions">
                <button className="ghost-button" disabled={mutating} onClick={() => void pinNow(lesson)}>
                  Pin now
                </button>
              </div>
            </div>
          ))}
          {lessons.length === 0 ? <p className="empty-panel">No lessons are currently bound to this course.</p> : null}
        </div>
      </article>

      <article className="portal-card portal-card--span-2">
        <header className="portal-card__header">
          <h2>Lesson timeline</h2>
          <div className="portal-inline-actions">
            <button className="ghost-button" disabled={mutating || lessons.length === 0} onClick={addWindow}>
              Add window
            </button>
            <button className="primary-button" disabled={mutating} onClick={() => void saveTimeline()}>
              Save timeline
            </button>
          </div>
        </header>
        {timelineError ? <p className="form-error">{timelineError}</p> : null}
        <div className="timeline-editor">
          {draftTimeline.map((window, index) => (
            <div className="timeline-editor__row" key={`${window.lesson_id}:${window.lesson_version}:${index}`}>
              <label>
                <span>Lesson</span>
                <select
                  value={`${window.lesson_id}:${window.lesson_version}`}
                  onChange={(event) => updateWindowLesson(index, event.target.value)}
                >
                  {lessonOptions.map((option) => (
                    <option key={option.key} value={option.key}>{option.label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Starts</span>
                <input
                  type="datetime-local"
                  value={window.starts_at}
                  onChange={(event) => updateWindow(index, { starts_at: event.target.value })}
                />
              </label>
              <label>
                <span>Ends</span>
                <input
                  type="datetime-local"
                  value={window.ends_at}
                  onChange={(event) => updateWindow(index, { ends_at: event.target.value })}
                />
              </label>
              <button className="ghost-button" disabled={mutating} onClick={() => removeWindow(index)}>
                Remove
              </button>
            </div>
          ))}
          {draftTimeline.length === 0 ? (
            <p className="empty-panel">No timeline windows are scheduled. Add a window or pin a lesson now.</p>
          ) : null}
        </div>
      </article>
    </section>
  )
}

export function InstructorLogsPanel({
  logs,
  selectedLog,
  selectedLogId,
  onOpenLog,
}: {
  logs: EncryptedLogMetadata[]
  selectedLog: Record<string, unknown> | null
  selectedLogId: string | null
  onOpenLog(sessionId: string): Promise<void>
}) {
  const [lessonFilter, setLessonFilter] = useState("")
  const [userFilter, setUserFilter] = useState("")

  const filteredLogs = useMemo(
    () =>
      logs.filter((log) => {
        const lessonMatch = !lessonFilter || log.lesson_id.toLowerCase().includes(lessonFilter.toLowerCase())
        const userMatch = !userFilter || log.user_id.toLowerCase().includes(userFilter.toLowerCase())
        return lessonMatch && userMatch
      }),
    [lessonFilter, logs, userFilter],
  )

  function renderStructuredLogPayload(payload: Record<string, unknown>) {
    const transcript = Array.isArray(payload.transcript) ? payload.transcript : null
    const reflections = Array.isArray(payload.reflections) ? payload.reflections : null

    if (transcript === null && reflections === null) {
      return <pre>{JSON.stringify(payload, null, 2)}</pre>
    }

    return (
      <div className="portal-list">
        <div className="portal-list__item portal-list__item--stack">
          <span className="portal-list__title">Session summary</span>
          <pre>{JSON.stringify(payload.session ?? {}, null, 2)}</pre>
        </div>
        {transcript ? (
          <div className="portal-list__item portal-list__item--stack">
            <span className="portal-list__title">Transcript</span>
            <pre>{JSON.stringify(transcript, null, 2)}</pre>
          </div>
        ) : null}
        {reflections ? (
          <div className="portal-list__item portal-list__item--stack">
            <span className="portal-list__title">Reflections</span>
            <pre>{JSON.stringify(reflections, null, 2)}</pre>
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <section className="portal-grid portal-grid--wide">
      <article className="portal-card portal-card--span-2">
        <header className="portal-card__header">
          <h2>Encrypted session logs</h2>
        </header>
        <div className="portal-inline-form">
          <input value={lessonFilter} onChange={(event) => setLessonFilter(event.target.value)} placeholder="Filter by lesson id" />
          <input value={userFilter} onChange={(event) => setUserFilter(event.target.value)} placeholder="Filter by user id" />
        </div>
        <div className="portal-log-grid">
          <div className="portal-list">
            {filteredLogs.map((log) => (
              <button
                key={log.instance_id}
                className={selectedLogId === log.instance_id ? "portal-list__item portal-list__item--active" : "portal-list__item"}
                onClick={() => void onOpenLog(log.instance_id)}
              >
                <span className="portal-list__title">{log.user_id}</span>
                <span className="portal-list__meta">
                  {log.lesson_id} · {log.turn_count} turns · {formatTimestamp(log.last_event_at)}
                </span>
              </button>
            ))}
            {filteredLogs.length === 0 ? <p className="empty-panel">No matching encrypted logs are currently available.</p> : null}
          </div>
          <div className="portal-log-preview">
            {selectedLog ? (
              renderStructuredLogPayload(selectedLog)
            ) : (
              <p className="empty-panel">Select a log to inspect its decrypted session payload.</p>
            )}
          </div>
        </div>
      </article>
    </section>
  )
}

export function InstructorAnalyticsPanel({
  lessons,
  logs,
}: {
  lessons: Lesson[]
  logs: EncryptedLogMetadata[]
}) {
  const totalTurns = logs.reduce((sum, log) => sum + log.turn_count, 0)
  const averageTurns = logs.length ? (totalTurns / logs.length).toFixed(1) : "0.0"
  const activeCount = logs.filter((log) => log.is_active).length
  const closedCount = logs.length - activeCount
  const sessionsByLesson = lessons.map((lesson) => {
    const count = logs.filter((log) => log.lesson_id === lesson.lesson_id && log.lesson_version === lesson.version).length
    return {
      key: `${lesson.lesson_id}:${lesson.version}`,
      label: lesson.title,
      count,
    }
  }).sort((left, right) => right.count - left.count)

  return (
    <section className="portal-grid portal-grid--wide">
      <article className="portal-card">
        <header className="portal-card__header"><h2>Activity summary</h2></header>
        <dl className="context-list">
          <div><dt>Total logged sessions</dt><dd>{logs.length}</dd></div>
          <div><dt>Active sessions</dt><dd>{activeCount}</dd></div>
          <div><dt>Closed sessions</dt><dd>{closedCount}</dd></div>
          <div><dt>Average turns per session</dt><dd>{averageTurns}</dd></div>
        </dl>
      </article>

      <article className="portal-card">
        <header className="portal-card__header"><h2>Recent activity</h2></header>
        <dl className="context-list">
          <div><dt>Most recent event</dt><dd>{logs.length ? formatTimestamp([...logs].sort((a, b) => b.last_event_at.localeCompare(a.last_event_at))[0].last_event_at) : "No activity yet"}</dd></div>
          <div><dt>Unique learners with logs</dt><dd>{new Set(logs.map((log) => log.user_id)).size}</dd></div>
        </dl>
      </article>

      <article className="portal-card portal-card--span-2">
        <header className="portal-card__header"><h2>Sessions by lesson</h2></header>
        <div className="portal-list">
          {sessionsByLesson.map((entry) => (
            <div key={entry.key} className="portal-list__item portal-list__item--split">
              <span className="portal-list__title">{entry.label}</span>
              <span className="section-chip">{entry.count} sessions</span>
            </div>
          ))}
          {sessionsByLesson.length === 0 ? <p className="empty-panel">No course lessons are available for analytics yet.</p> : null}
        </div>
      </article>
    </section>
  )
}

export function InstructorRosterPanel({
  course,
  instructors,
  pendingRequests,
  mutating,
  addInstructorUserId,
  setAddInstructorUserId,
  onAddInstructor,
  onRemoveInstructor,
  onApproveRequest,
  onRemoveStudent,
}: {
  course: Course
  instructors: CourseInstructors
  pendingRequests: string[]
  mutating: boolean
  addInstructorUserId: string
  setAddInstructorUserId(value: string): void
  onAddInstructor(): Promise<void>
  onRemoveInstructor(userId: string): Promise<void>
  onApproveRequest(userId: string): Promise<void>
  onRemoveStudent(userId: string): Promise<void>
}) {
  return (
    <section className="portal-grid portal-grid--wide">
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
          <button className="primary-button" disabled={mutating} onClick={() => void onAddInstructor()}>
            Add instructor
          </button>
        </div>
        <div className="portal-list">
          {instructors.instructor_ids.map((userId) => (
            <div key={userId} className="portal-list__item portal-list__item--split">
              <span className="portal-list__title">{userId}</span>
              {userId !== instructors.owner_id ? (
                <button className="ghost-button" disabled={mutating} onClick={() => void onRemoveInstructor(userId)}>
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
              <button className="primary-button" disabled={mutating} onClick={() => void onApproveRequest(userId)}>
                Approve
              </button>
            </div>
          ))}
          {course.enrolled_users.map((userId) => (
            <div key={`enrolled:${userId}`} className="portal-list__item portal-list__item--split">
              <span className="portal-list__title">{userId}</span>
              <button className="ghost-button" disabled={mutating} onClick={() => void onRemoveStudent(userId)}>
                Remove
              </button>
            </div>
          ))}
          {pendingRequests.length === 0 && course.enrolled_users.length === 0 ? (
            <p className="empty-panel">No roster activity yet.</p>
          ) : null}
        </div>
      </article>
    </section>
  )
}
