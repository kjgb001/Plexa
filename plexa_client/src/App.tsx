import { useState } from "react"
import LoginScreen from "./screens/LoginScreen"
import CourseListScreen from "./screens/CourseListScreen"
import LessonListScreen from "./screens/LessonListScreen"
import ChatScreen from "./screens/ChatScreen"

type Screen = "courses" | "lessons" | "chat"

export default function App() {
  const [loggedIn, setLoggedIn] = useState(
    !!localStorage.getItem("plexa_user")
  )

  const [screen, setScreen] = useState<Screen>("courses")
  const [courseId, setCourseId] = useState<string | null>(null)
  const [lessonId, setLessonId] = useState<string | null>(null)
  const [lessonVersion, setLessonVersion] = useState<string | null>(null)

  if (!loggedIn) {
    return <LoginScreen onLogin={() => setLoggedIn(true)} />
  }

  if (screen === "courses") {
    return (
      <CourseListScreen
        onSelectCourse={(course) => {
          setCourseId(course)
          setScreen("lessons")
        }}
      />
    )
  }

  if (screen === "lessons" && courseId) {
    return (
      <LessonListScreen
        courseId={courseId}
        onSelectLesson={(lessonId, lessonVersion) => {
          setLessonId(lessonId)
          setLessonVersion(lessonVersion)
          setScreen("chat")
        }}
      />
    )
  }

  if (screen === "chat" && courseId && lessonId && lessonVersion) {
    return (
      <ChatScreen
        courseId={courseId}
        lessonId={lessonId}
        lessonVersion={lessonVersion}
      />
    )
  }

  return null
}