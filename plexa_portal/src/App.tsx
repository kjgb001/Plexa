import { useEffect } from "react"
import BootScreen from "./app/BootScreen"
import AuthCallbackScreen from "./app/AuthCallbackScreen"
import { navigate, parseRoute, studentPaths, useCurrentPathname } from "./app/router"
import { useAuth } from "./auth/useAuth"
import { ApiProvider } from "./api"
import LoginScreen from "./screens/LoginScreen"
import { StudentApp } from "./student/StudentApp"
import { InstructorApp } from "./instructor/InstructorApp"

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
  const { mode, status, user, error, login, logout } = useAuth()

  useEffect(() => {
    if (status === "authenticated" && route.kind === "login") {
      navigate(studentPaths.courses(), { replace: true })
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
        <h1>Plexa Portal</h1>
        <p>Authentication failed during app boot.</p>
        <pre>{error?.message}</pre>
      </div>
    )
  }

  if (status !== "authenticated") {
    return (
      <LoginScreen
        mode={mode}
        onLogin={async (userId) => {
          await login(userId)
        }}
      />
    )
  }

  if (route.kind === "not-found") {
    return (
      <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
        <h1>Plexa Portal</h1>
        <p>Page not found.</p>
      </div>
    )
  }

  if (route.kind === "login") {
    return null
  }

  if (route.surface === "student") {
    return (
      <StudentApp
        route={route}
        userId={user?.userId ?? null}
        onLogout={logout}
      />
    )
  }

  return (
    <InstructorApp
      route={route}
      userId={user?.userId ?? null}
      onLogout={logout}
    />
  )
}
