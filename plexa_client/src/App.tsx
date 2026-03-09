import { useEffect, useState } from "react"
import { courseApi } from "./api"
import type { Course } from "./api/types"

export default function App() {
  const [courses, setCourses] = useState<Course[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadCourses() {
      try {
        const result = await courseApi.listDiscoverable()
        setCourses(result.courses)
      } catch (err) {
        console.error(err)
        setError("Failed to load courses")
      }
    }

    loadCourses()
  }, [])

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa</h1>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <h2>Courses</h2>

      {courses.length === 0 && <p>No courses found.</p>}

      <ul>
        {courses.map(course => (
          <li key={course.course_id}>
            {course.title} ({course.course_id})
          </li>
        ))}
      </ul>
    </div>
  )
}