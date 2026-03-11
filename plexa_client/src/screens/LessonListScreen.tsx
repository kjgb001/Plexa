import { useEffect, useState } from "react"
import { courseApi } from "../api"
import type { Lesson } from "../api/interfaces"

interface Props {
  courseId: string
  onSelectLesson: (lessonId: string, lessonVersion:string) => void
}

export default function LessonListScreen({ courseId, onSelectLesson }: Props) {
  const [lessons, setLessons] = useState<Lesson[]>([])

  useEffect(() => {
    async function loadLessons() {
      try {
        const result = await courseApi.listLessons(courseId)
        console.log(result.lessons)
        setLessons(result.lessons ?? [])
      } catch (err) {
        console.error("Failed to load lessons", err)
        setLessons([])
      }
    }
    loadLessons()
  }, [courseId])

  return (
    <div>
      <h1>Lessons</h1>

      {lessons.map((lesson) => (
        <div
          key={lesson.lesson_id}
          onClick={() => onSelectLesson(lesson.lesson_id, lesson.version)}
          style={{
            cursor: "pointer",
            border: "1px solid #ccc",
            padding: "10px",
            marginBottom: "10px"
          }}
        >
          {lesson.title}
        </div>
      ))}
    </div>
  )
}