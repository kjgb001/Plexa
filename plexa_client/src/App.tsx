import { useEffect } from "react"
import BootScreen from "./app/BootScreen"
import AuthCallbackScreen from "./app/AuthCallbackScreen"
import { navigate, parseRoute, useCurrentPathname } from "./app/router"
import { useAuth } from "./auth/useAuth"
import { ApiProvider } from "./api"
import StudentShell from "./app/StudentShell"
import LoginScreen from "./screens/LoginScreen"
import CourseListScreen from "./screens/CourseListScreen"
import LessonListScreen from "./screens/LessonListScreen"
import ChatScreen from "./screens/ChatScreen"

export default function App() {
  return (
    <ApiProvider>
      <AppView />
    </ApiProvider>
  )
}

function AppView() {
  const pathname = useCurrentPathname()
  const route = parseRoute(pathname)
  const { status, user, error, login, logout } = useAuth()

  useEffect(() => {
    if (status === "authenticated" && route.kind === "login") {
      navigate("/app/courses", { replace: true })
    }
  }, [route.kind, status])

  if (status === "booting") {
    return <BootScreen />
  }

  if (route.kind === "auth-callback") {
    return <AuthCallbackScreen />
  }

  if (status === "error") {
    return (
      <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
        <h1>Plexa</h1>
        <p>Authentication failed during app boot.</p>
        <pre>{error?.message}</pre>
      </div>
    )
  }

  if (status !== "authenticated") {
    return (
      <LoginScreen
        onLogin={async (userId) => {
          await login(userId)
          navigate("/app/courses", { replace: true })
        }}
      />
    )
  }

  if (route.kind === "courses") {
    return (
      <StudentShell route={route} userId={user?.userId ?? null} onLogout={logout}>
        <CourseListScreen
          onSelectCourse={(course) => {
            navigate(`/app/courses/${encodeURIComponent(course)}`)
          }}
        />
      </StudentShell>
    )
  }

  if (route.kind === "lessons") {
    return (
      <StudentShell route={route} userId={user?.userId ?? null} onLogout={logout}>
        <LessonListScreen
          courseId={route.courseId}
          onSelectLesson={(lessonId, lessonVersion) => {
            navigate(
              `/app/courses/${encodeURIComponent(route.courseId)}/lessons/${encodeURIComponent(lessonId)}/${encodeURIComponent(lessonVersion)}`
            )
          }}
        />
      </StudentShell>
    )
  }

  if (route.kind === "chat") {
    return (
      <StudentShell route={route} userId={user?.userId ?? null} onLogout={logout}>
        <ChatScreen
          courseId={route.courseId}
          lessonId={route.lessonId}
          lessonVersion={route.lessonVersion}
          sessionId={route.sessionId}
        />
      </StudentShell>
    )
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa</h1>
      <p>Page not found.</p>
    </div>
  )
}
