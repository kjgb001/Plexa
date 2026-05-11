import { useEffect, type ReactNode } from "react"
import BootScreen from "./app/BootScreen"
import AuthCallbackScreen from "./app/AuthCallbackScreen"
import { navigate, parseRoute, useCurrentPathname, type AppRoute } from "./app/router"
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
      <AuthenticatedAppShell route={route} userId={user?.userId ?? null} onLogout={logout} />
    )
  }

  if (route.kind === "lessons") {
    return (
      <AuthenticatedAppShell route={route} userId={user?.userId ?? null} onLogout={logout} />
    )
  }

  if (route.kind === "chat") {
    return (
      <AuthenticatedAppShell route={route} userId={user?.userId ?? null} onLogout={logout} />
    )
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa</h1>
      <p>Page not found.</p>
    </div>
  )
}

function AuthenticatedAppShell({
  route,
  userId,
  onLogout,
}: {
  route: Exclude<AppRoute, { kind: "login" | "auth-callback" | "not-found" }>
  userId: string | null
  onLogout: () => Promise<void>
}) {
  let content: ReactNode

  if (route.kind === "courses") {
    content = (
      <CourseListScreen
        onSelectCourse={(course) => {
          navigate(`/app/courses/${encodeURIComponent(course)}`)
        }}
      />
    )
  } else if (route.kind === "lessons") {
    content = (
      <LessonListScreen
        courseId={route.courseId}
        onSelectLesson={(lessonId, lessonVersion) => {
          navigate(
            `/app/courses/${encodeURIComponent(route.courseId)}/lessons/${encodeURIComponent(lessonId)}/${encodeURIComponent(lessonVersion)}`,
          )
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
