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
    <section className="screen-card">
      <div className="screen-card__header">
        <div>
          <p className="eyebrow">Course Discovery</p>
          <h1>Choose a course space</h1>
          <p>
            Start from a course home, then narrow into one lesson workspace. The
            shell stays stable so students can move around without losing context.
          </p>
        </div>
      </div>

      {loading ? <p>Loading available courses...</p> : null}

      {!loading && courses.length === 0 ? (
        <div className="empty-panel">
          No discoverable courses are available for this account yet.
        </div>
      ) : null}

      <div className="rail__list">
        {courses.map((course) => (
          <button
            key={course.course_id}
            className="rail-card"
            onClick={() => onSelectCourse(course.course_id)}
          >
            <span className="rail-card__title">{course.title}</span>
            <span className="rail-card__meta">
              {course.description ?? "Enter to browse lessons and begin a session."}
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}
