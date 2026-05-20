import { useMemo, useState } from "react"
import type { Course, CourseInstructors, EncryptedLogMetadata, Lesson } from "../../api/interfaces"

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Unavailable"
  }
  return new Date(value).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  })
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
  lessons,
}: {
  lessons: Lesson[]
}) {
  return (
    <section className="portal-grid portal-grid--wide">
      <article className="portal-card portal-card--span-2">
        <header className="portal-card__header">
          <h2>Lessons in course</h2>
        </header>
        <p className="portal-note">
          Timeline editing still needs dedicated server mutation support. This panel reflects the current server ordering and pinned state.
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
            </div>
          ))}
          {lessons.length === 0 ? <p className="empty-panel">No lessons are currently bound to this course.</p> : null}
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
              <pre>{JSON.stringify(selectedLog, null, 2)}</pre>
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
