import { useEffect, useState } from "react"
import { useApis } from "../api"
import type { Course } from "../api/interfaces"

interface Props {
  onSelectCourse: (courseId: string) => void
}

export default function CourseListScreen({ onSelectCourse }: Props) {
  const { courseApi } = useApis()
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)

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
    <section className="catalog-stage catalog-stage--courses" aria-labelledby="course-stage-title">
      <header className="catalog-stage__hero">
        <p className="eyebrow">Course Discovery</p>
        <h1 id="course-stage-title">Choose a course workspace</h1>
        <p className="catalog-stage__summary">
          Plexa is organized like an academic studio. Start with the course,
          narrow into a lesson, then work through sessions that capture your
          reasoning over time.
        </p>
      </header>

      <section className="catalog-stage__body" aria-label="Course browser">
        <aside className="catalog-stage__brief">
          <h2>How students move through the workspace</h2>
          <p>
            Course selection sets the frame. The lesson defines the objective.
            Sessions hold each attempt, reflection, and revision.
          </p>
          <dl className="catalog-stage__facts">
            <div>
              <dt>Step 1</dt>
              <dd>Choose the course context.</dd>
            </div>
            <div>
              <dt>Step 2</dt>
              <dd>Open the lesson you want to work on.</dd>
            </div>
            <div>
              <dt>Step 3</dt>
              <dd>Resume an older session or start a fresh one.</dd>
            </div>
          </dl>
        </aside>

        <section className="catalog-stage__rail" aria-label="Available courses">
          <header className="catalog-stage__section-header">
            <h2>Available Courses</h2>
            <p>Each course becomes a stable workspace in the left rail.</p>
          </header>

          {loading ? <p className="status-note">Loading available courses...</p> : null}

          {loading === false && courses.length === 0 ? (
            <p className="empty-panel" role="status">
              No discoverable courses are available for this account yet.
            </p>
          ) : null}

          <ol className="catalog-list">
            {courses.map((course, index) => (
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
                    <p>Open the course to view lesson workspaces and session history.</p>
                    <button
                      className="catalog-entry__action"
                      onClick={() => onSelectCourse(course.course_id)}
                    >
                      Open course
                    </button>
                  </footer>
                </article>
              </li>
            ))}
          </ol>
        </section>
      </section>
    </section>
  )
}
