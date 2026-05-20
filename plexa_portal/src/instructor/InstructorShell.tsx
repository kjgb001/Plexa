import type { ReactNode } from "react"
import { instructorPaths, navigate, studentPaths, type InstructorRoute } from "../app/router"
import { useTheme } from "../theme/useTheme"

export function InstructorShell({
  route,
  userId,
  onLogout,
  children,
}: {
  route: InstructorRoute
  userId: string | null
  onLogout(): Promise<void>
  children: ReactNode
}) {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="portal-shell portal-shell--instructor">
      <aside className="portal-shell__rail">
        <div className="portal-shell__brand">
          <p className="eyebrow">Instructor Portal</p>
          <h1>Plexa Portal</h1>
          <div className="portal-shell__actions">
            <button className="ghost-button" onClick={() => navigate(instructorPaths.home())}>
              Courses
            </button>
            <button className="ghost-button" onClick={() => navigate(studentPaths.courses())}>
              Student view
            </button>
            <button className="ghost-button" onClick={toggleTheme}>
              {theme === "light" ? "Dark mode" : "Light mode"}
            </button>
            <button
              className="ghost-button"
              onClick={() => {
                void onLogout().then(() => {
                  navigate("/login", { replace: true })
                })
              }}
            >
              Logout
            </button>
          </div>
        </div>

        <div className="portal-shell__rail-body">
          <section className="context-panel">
            <header className="context-panel__header">
              <p className="eyebrow">Portal State</p>
            </header>
            <dl className="context-list">
              <div>
                <dt>Viewer</dt>
                <dd>{userId ?? "Unknown user"}</dd>
              </div>
              <div>
                <dt>Section</dt>
                <dd>{route.kind === "home" ? "Course overview" : "Course workspace"}</dd>
              </div>
              {route.kind === "course" ? (
                <div>
                  <dt>Course</dt>
                  <dd>{route.courseId}</dd>
                </div>
              ) : null}
            </dl>
          </section>
        </div>
      </aside>

      <section className="portal-shell__main">
        <main className="workspace-main">{children}</main>
      </section>
    </div>
  )
}
