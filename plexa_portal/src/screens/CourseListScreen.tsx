import { useEffect, useMemo, useState } from "react"
import { useApis } from "../api"
import type { Course } from "../api/interfaces"
import { getRememberedPortalChoice } from "../auth/portalEntry"
import { useAuth } from "../auth/useAuth"

interface Props {
  onSelectCourse: (courseId: string) => void
}

export default function CourseListScreen({ onSelectCourse }: Props) {
  const { courseApi } = useApis()
  const { user } = useAuth()
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [requestState, setRequestState] = useState<Record<string, string>>({})

  const canUseInstructorPortal = getRememberedPortalChoice() === "instructor"
  const currentUserId = user?.userId ?? null

  useEffect(() => {
    let active = true

    async function loadCourses() {
      try {
        const result = await courseApi.listDiscoverable()

        if (active) {
          setCourses(result.courses)
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadCourses()

    return () => {
      active = false
    }
  }, [courseApi])

  const filteredCourses = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) {
      return courses
    }

    return courses.filter((course) =>
      course.course_id.toLowerCase().includes(query)
      || course.title.toLowerCase().includes(query)
      || (course.description ?? "").toLowerCase().includes(query),
    )
  }, [courses, search])

  async function handleRequestEnrollment(courseId: string) {
    setRequestState((current) => ({ ...current, [courseId]: "Requesting..." }))
    try {
      const result = await courseApi.requestEnrollment(courseId)
      const nextStatus =
        result.status === "already_enrolled"
          ? "Already enrolled"
          : result.status === "pending"
            ? "Enrollment requested"
            : result.status
      setRequestState((current) => ({ ...current, [courseId]: nextStatus }))
      setCourses((current) =>
        current.map((course) =>
          course.course_id === courseId
            ? {
                ...course,
                pending_requests: currentUserId
                  ? Array.from(new Set([...(course.pending_requests ?? []), currentUserId]))
                  : course.pending_requests,
              }
            : course,
        ),
      )
    } catch {
      setRequestState((current) => ({ ...current, [courseId]: "Request failed" }))
    }
  }

  return (
    <section className="catalog-stage catalog-stage--courses catalog-stage--lessons" aria-labelledby="course-stage-title">
      <header className="catalog-stage__hero catalog-stage__hero--sticky">
        <p className="eyebrow">Course Discovery</p>
        <h1 id="course-stage-title">Choose a course workspace</h1>
        <p className="catalog-stage__summary">
          Plexa is organized like an academic studio. Start with the course,
          narrow into a lesson, then work through sessions that capture your
          reasoning over time.
        </p>
      </header>

      <section className="catalog-stage__body catalog-stage__body--lessons" aria-label="Course browser">
        <section className="catalog-stage__rail catalog-stage__rail--scroll" aria-label="Available courses">
          <header className="catalog-stage__section-header">
            <h2>Available Courses</h2>
            <p>Each course becomes a stable workspace in the left rail.</p>
          </header>

          <div className="portal-inline-form">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by course id, title, or description"
            />
          </div>

          {loading ? <p className="status-note">Loading available courses...</p> : null}

          {loading === false && filteredCourses.length === 0 ? (
            <p className="empty-panel" role="status">
              No discoverable courses match the current search.
            </p>
          ) : null}

          <ol className="catalog-list">
            {filteredCourses.map((course, index) => {
              const isOwner = currentUserId !== null && course.owner_id === currentUserId
              const isEnrolled = currentUserId !== null && course.enrolled_users.includes(currentUserId)
              const isPending = currentUserId !== null && (course.pending_requests ?? []).includes(currentUserId)
              const canOpenCourse = isOwner || isEnrolled || canUseInstructorPortal

              return (
              <li key={course.course_id}>
                <article className="catalog-entry catalog-entry--course">
                  <header className="catalog-entry__header">
                    <p className="catalog-entry__index">{String(index + 1).padStart(2, "0")}</p>
                    <div>
                      <p className="catalog-entry__eyebrow">Course</p>
                      <h3>{course.title}</h3>
                    </div>
                    <span className="section-chip">{course.course_id}</span>
                  </header>
                  <p className="catalog-entry__description">
                    {course.description ?? "Browse lessons and reopen prior study sessions."}
                  </p>
                  <footer className="catalog-entry__footer">
                    <div className="catalog-entry__footer-copy">
                      <p>
                        {canOpenCourse
                          ? "Open the course to view lesson workspaces and session history."
                          : isPending
                            ? "Enrollment request pending."
                            : "Request enrollment before opening the student workspace."}
                      </p>
                      {requestState[course.course_id] ? (
                        <p className="status-note">{requestState[course.course_id]}</p>
                      ) : null}
                    </div>
                    <div className="catalog-entry__footer-actions">
                      {canOpenCourse ? (
                        <button
                          className="catalog-entry__action"
                          onClick={() => onSelectCourse(course.course_id)}
                        >
                          Open course
                        </button>
                      ) : (
                        <button
                          className="catalog-entry__action"
                          onClick={() => void handleRequestEnrollment(course.course_id)}
                          disabled={isPending || requestState[course.course_id] === "Requesting..."}
                        >
                          {isPending ? "Enrollment pending" : "Request enrollment"}
                        </button>
                      )}
                    </div>
                  </footer>
                </article>
              </li>
            )})}
          </ol>
        </section>
      </section>
    </section>
  )
}
