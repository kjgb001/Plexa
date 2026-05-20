import type { ReactNode } from "react"
import { navigate, studentPaths, type StudentRoute } from "../app/router"
import StudentShell from "../app/StudentShell"
import ChatScreen from "../screens/ChatScreen"
import CourseListScreen from "../screens/CourseListScreen"
import LessonListScreen from "../screens/LessonListScreen"

export function StudentApp({
  route,
  userId,
  onLogout,
}: {
  route: StudentRoute
  userId: string | null
  onLogout(): Promise<void>
}) {
  let content: ReactNode

  if (route.kind === "courses") {
    content = (
      <CourseListScreen
        onSelectCourse={(course) => {
          navigate(studentPaths.lessons(course))
        }}
      />
    )
  } else if (route.kind === "lessons") {
    content = (
      <LessonListScreen
        courseId={route.courseId}
        onSelectLesson={(lessonId, lessonVersion) => {
          navigate(studentPaths.chat(route.courseId, lessonId, lessonVersion))
        }}
      />
    )
  } else {
    content = (
      <ChatScreen
        courseId={route.courseId}
        lessonId={route.lessonId}
        lessonVersion={route.lessonVersion}
        sessionId={route.sessionId}
      />
    )
  }

  return (
    <StudentShell route={route} userId={userId} onLogout={onLogout}>
      {content}
    </StudentShell>
  )
}
