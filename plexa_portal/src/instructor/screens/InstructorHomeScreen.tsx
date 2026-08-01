import { useEffect, useState } from "react"
import { useApis } from "../../api"
import type { Course } from "../../api/interfaces"
import { useAuth } from "../../auth/useAuth"

export function InstructorHomeScreen({
  onOpenCourse,
}: {
  onOpenCourse(courseId: string): void
}) {
  const { instructorApi } = useApis()
  const { user } = useAuth()
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [lookupCourseId, setLookupCourseId] = useState("")

  useEffect(() => {
    let active = true

    async function loadCourses() {
      try {
        const result = await instructorApi.listCourses()
        if (active) {
          const allowed = new Set(user?.instructedCourseIds ?? [])
          setCourses(
            user?.isAdmin
              ? result
              : result.filter((course) => allowed.has(course.course_id)),
          )
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
  }, [instructorApi, user?.instructedCourseIds, user?.isAdmin])

  return (
    <section className="portal-stage" aria-labelledby="instructor-home-title">
      <header className="portal-stage__hero">
        <p className="eyebrow">Instructor Workspace</p>
        <h1 id="instructor-home-title">Course operations</h1>
        <p className="portal-stage__summary">
          Open a course to work inside explicit instructor tools: Overview, Lessons, Builder, Logs, Analytics, and Roster.
        </p>
      </header>

      <section className="portal-grid">
        <article className="portal-card">
          <header className="portal-card__header">
            <h2>Open a course</h2>
          </header>
          <p>
            Courses assigned to your authenticated instructor account appear below.
          </p>
          <div className="portal-inline-form">
            <input
              value={lookupCourseId}
              onChange={(event) => setLookupCourseId(event.target.value)}
              placeholder="CS101"
            />
            <button
              className="primary-button"
              onClick={() => {
                if (!lookupCourseId.trim()) {
                  return
                }
                onOpenCourse(lookupCourseId.trim())
              }}
            >
              Open course
            </button>
          </div>
        </article>

        <article className="portal-card">
          <header className="portal-card__header">
            <h2>Your courses</h2>
          </header>
          {loading ? <p className="status-note">Loading courses...</p> : null}
          {!loading && courses.length === 0 ? (
            <p className="empty-panel">No courses are assigned to this account.</p>
          ) : null}
          <div className="portal-list">
            {courses.map((course) => (
              <button
                key={course.course_id}
                className="portal-list__item"
                onClick={() => onOpenCourse(course.course_id)}
              >
                <span className="portal-list__title">{course.title}</span>
                <span className="portal-list__meta">
                  {course.course_id}{course.archived_at ? " | Archived" : ""}
                </span>
              </button>
            ))}
          </div>
        </article>
      </section>
    </section>
  )
}
