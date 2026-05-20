import { useEffect, useState } from "react"
import { useApis } from "../../api"
import type { Course } from "../../api/interfaces"

export function InstructorHomeScreen({
  onOpenCourse,
}: {
  onOpenCourse(courseId: string): void
}) {
  const { courseApi } = useApis()
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [lookupCourseId, setLookupCourseId] = useState("")

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
            Discoverable courses appear below. If you manage a course that is not discoverable,
            open it directly by course ID.
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
            <h2>Discoverable courses</h2>
          </header>
          {loading ? <p className="status-note">Loading courses...</p> : null}
          {!loading && courses.length === 0 ? (
            <p className="empty-panel">No discoverable courses are currently visible.</p>
          ) : null}
          <div className="portal-list">
            {courses.map((course) => (
              <button
                key={course.course_id}
                className="portal-list__item"
                onClick={() => onOpenCourse(course.course_id)}
              >
                <span className="portal-list__title">{course.title}</span>
                <span className="portal-list__meta">{course.course_id}</span>
              </button>
            ))}
          </div>
        </article>
      </section>
    </section>
  )
}
