import BootScreen from "./app/BootScreen"
import AuthCallbackScreen from "./app/AuthCallbackScreen"
import { navigate, instructorPaths, parseRoute, studentPaths, useCurrentPathname } from "./app/router"
import { getRememberedPortalChoice, rememberPortalChoice, rememberPostLoginPath } from "./auth/portalEntry"
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

  if (status === "authenticated" && route.kind === "login") {
    navigate(
      getRememberedPortalChoice() === "instructor"
        ? instructorPaths.home()
        : studentPaths.courses(),
      { replace: true },
    )
    return null
  }

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
        onLogin={async ({ userId, portal }) => {
          const nextPath = portal === "instructor"
            ? instructorPaths.home()
            : studentPaths.courses()
          rememberPortalChoice(portal)
          rememberPostLoginPath(nextPath)
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

  if (!user?.canAccessInstructorPortal) {
    return (
      <div className="portal-stage">
        <h1>Instructor access unavailable</h1>
        <p>Your authenticated account does not manage or teach any Plexa courses.</p>
        <button className="primary-button" onClick={() => navigate(studentPaths.courses())}>
          Open student portal
        </button>
      </div>
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
