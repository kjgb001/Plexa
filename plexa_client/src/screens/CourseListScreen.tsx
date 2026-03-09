import { useEffect, useState } from "react"
import { courseApi } from "../api"
import type { Course } from "../api/types"

export default function CourseListScreen() {
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadCourses() {
      const result = await courseApi.listDiscoverable()
      setCourses(result.courses)
      setLoading(false)
    }

    loadCourses()
  }, [])

  if (loading) {
    return <p>Loading courses...</p>
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Available Courses</h1>

      {courses.length === 0 && <p>No discoverable courses.</p>}

      <ul>
        {courses.map(course => (
          <li key={course.course_id}>
            {course.title}
          </li>
        ))}
      </ul>
    </div>
  )
}