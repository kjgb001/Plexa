import { useEffect, useState } from "react"
import { courseApi } from "../api"
import type { Course } from "../api/interfaces"

interface Props {
  onSelectCourse: (courseId: string) => void
}

export default function CourseListScreen({ onSelectCourse }: Props) {
  const [courses, setCourses] = useState<Course[]>([])

  useEffect(() => {
    courseApi.listDiscoverable().then(result => {
      setCourses(result.courses)
    })
  }, [])

  return (
    <div>
      <h1>Courses</h1>

      {courses.map((course) => (
        <div
          key={course.course_id}
          onClick={() => onSelectCourse(course.course_id)}
          style={{
            cursor: "pointer",
            border: "1px solid #ccc",
            padding: "10px",
            marginBottom: "10px"
          }}
        >
          {course.title}
        </div>
      ))}
    </div>
  )
}