import { useEffect, useState } from "react"
import { useApis } from "../../api"
import { ApiError, NotFoundError } from "../../api/errors"
import type { Course, CourseInstructors, CourseLessonWindow, EncryptedLogMetadata, Lesson } from "../../api/interfaces"
import { instructorPaths, navigate } from "../../app/router"
import { InstructorBuilderPanel } from "./InstructorBuilderPanel"
import {
  InstructorAnalyticsPanel,
  InstructorLessonsPanel,
  InstructorLogsPanel,
  InstructorOverviewPanel,
  InstructorRosterPanel,
} from "./InstructorCoursePanels"

type InstructorMode = "overview" | "lessons" | "builder" | "logs" | "analytics" | "roster"

export function InstructorCourseScreen({
  courseId,
  mode,
  logSessionId = null,
}: {
  courseId: string
  mode: InstructorMode
  logSessionId?: string | null
}) {
  const { instructorApi } = useApis()
  const [course, setCourse] = useState<Course | null>(null)
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [instructors, setInstructors] = useState<CourseInstructors | null>(null)
  const [pendingRequests, setPendingRequests] = useState<string[]>([])
  const [logs, setLogs] = useState<EncryptedLogMetadata[]>([])
  const [selectedLog, setSelectedLog] = useState<Record<string, unknown> | null>(null)
  const [selectedLogLoading, setSelectedLogLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [addInstructorUserId, setAddInstructorUserId] = useState("")
  const [mutating, setMutating] = useState(false)

  async function loadWorkspace() {
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

      setCourse(courseResult)
      setLessons(lessonsResult)
      setInstructors(instructorsResult)
      setPendingRequests(requests)
      setLogs(logsResult)
    } catch (error) {
      console.error("Failed to load instructor course workspace", error)
      if (error instanceof NotFoundError) {
        setLoadError("This course is not available to your instructor account.")
      } else {
        setLoadError("Failed to load course workspace.")
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadWorkspace()
  }, [courseId, instructorApi])

  useEffect(() => {
    let active = true

    async function loadSelectedLog() {
      if (logSessionId === null) {
        setSelectedLog(null)
        return
      }

      setSelectedLog(null)
      setSelectedLogLoading(true)
      try {
        const payload = await instructorApi.getLog(courseId, logSessionId)
        if (active) {
          setSelectedLog(payload)
        }
      } catch (error) {
        console.error("Failed to load instructor log detail", error)
        if (active) {
          setSelectedLog({ error: "Failed to load log detail." })
        }
      } finally {
        if (active) {
          setSelectedLogLoading(false)
        }
      }
    }

    void loadSelectedLog()

    return () => {
      active = false
    }
  }, [courseId, instructorApi, logSessionId])

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
    navigate(instructorPaths.logDetail(courseId, sessionId))
  }

  async function handleUpdateLessonTimeline(lessonTimeline: CourseLessonWindow[]) {
    setMutating(true)
    try {
      const nextTimeline = await instructorApi.updateLessonTimeline(courseId, lessonTimeline)
      const lessonsResult = await instructorApi.listLessons(courseId)
      setCourse((current) => current ? { ...current, lesson_timeline: nextTimeline } : current)
      setLessons(lessonsResult)
    } finally {
      setMutating(false)
    }
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
          This course workspace is organized around explicit tools. Use Overview for operational state, Lessons for sequencing context, Builder for lesson authoring, Logs for transcript review, Analytics for aggregate patterns, and Roster for membership control.
        </p>
      </header>

      {mode === "overview" ? (
        <InstructorOverviewPanel
          course={course}
          instructors={instructors}
          pendingRequests={pendingRequests}
          lessons={lessons}
          logs={logs}
        />
      ) : null}

      {mode === "lessons" ? (
        <InstructorLessonsPanel
          course={course}
          lessons={lessons}
          mutating={mutating}
          onUpdateTimeline={handleUpdateLessonTimeline}
        />
      ) : null}

      {mode === "builder" ? (
        <InstructorBuilderPanel
          courseId={courseId}
          lessons={lessons}
          onLessonBound={loadWorkspace}
        />
      ) : null}

      {mode === "logs" ? (
        <InstructorLogsPanel
          logs={logs}
          lessons={lessons}
          selectedLog={selectedLog}
          selectedLogId={logSessionId}
          selectedLogLoading={selectedLogLoading}
          onOpenLog={handleOpenLog}
          onBackToLogs={() => navigate(instructorPaths.course(courseId, "logs"))}
        />
      ) : null}

      {mode === "analytics" ? (
        <InstructorAnalyticsPanel lessons={lessons} logs={logs} />
      ) : null}

      {mode === "roster" ? (
        <InstructorRosterPanel
          course={course}
          instructors={instructors}
          pendingRequests={pendingRequests}
          mutating={mutating}
          addInstructorUserId={addInstructorUserId}
          setAddInstructorUserId={setAddInstructorUserId}
          onAddInstructor={handleAddInstructor}
          onRemoveInstructor={handleRemoveInstructor}
          onApproveRequest={handleApproveRequest}
          onRemoveStudent={handleRemoveStudent}
        />
      ) : null}
    </section>
  )
}
