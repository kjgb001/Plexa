import { useEffect, useMemo, useState, type ReactNode } from "react"
import { useApis } from "../api"
import type { Course } from "../api/interfaces"
import { instructorPaths, navigate, studentPaths, type InstructorRoute } from "../app/router"
import { useTheme } from "../theme/useTheme"

function visibleInstructorCourses(
  items: Course[],
  expanded: boolean,
  selectedCourseId: string | null,
  limit = 4,
) {
  if (expanded || items.length <= limit) {
    return items
  }

  const selectedIndex = items.findIndex((course) => course.course_id === selectedCourseId)
  if (selectedIndex === -1 || selectedIndex < limit) {
    return items.slice(0, limit)
  }

  return [...items.slice(0, limit - 1), items[selectedIndex]]
}

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
  const { courseApi } = useApis()
  const { theme, toggleTheme } = useTheme()
  const [courses, setCourses] = useState<Course[]>([])
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [coursesExpanded, setCoursesExpanded] = useState(false)
  const selectedCourseId = route.kind === "course" || route.kind === "log-detail" ? route.courseId : null
  const selectedMode = route.kind === "log-detail" ? "logs" : route.kind === "course" ? route.mode : null

  useEffect(() => {
    let active = true

    async function loadCourses() {
      setCoursesLoading(true)

      try {
        const result = await courseApi.listDiscoverable()
        if (active) {
          setCourses(result.courses)
        }
      } catch {
        if (active) {
          setCourses([])
        }
      } finally {
        if (active) {
          setCoursesLoading(false)
        }
      }
    }

    void loadCourses()

    return () => {
      active = false
    }
  }, [courseApi])

  const visibleCourses = useMemo(
    () => visibleInstructorCourses(courses, coursesExpanded, selectedCourseId),
    [courses, coursesExpanded, selectedCourseId],
  )

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
          <section className="portal-shell__mode-nav">
            <header className="context-panel__header">
              <p className="eyebrow">Courses</p>
            </header>
            <div className="portal-list">
              {coursesLoading ? <div className="empty-panel">Loading courses...</div> : null}
              {!coursesLoading && visibleCourses.map((course) => (
                <button
                  key={course.course_id}
                  className={
                    course.course_id === selectedCourseId
                      ? "portal-list__item portal-list__item--active"
                      : "portal-list__item"
                  }
                  onClick={() => navigate(instructorPaths.course(course.course_id, "overview"))}
                >
                  <span className="portal-list__title">{course.title}</span>
                  <span className="portal-list__meta">{course.course_id}</span>
                </button>
              ))}
              {!coursesLoading && courses.length > 4 ? (
                <button
                  className="ghost-button"
                  onClick={() => setCoursesExpanded((current) => !current)}
                >
                  {coursesExpanded ? "Show Less" : "Show More"}
                </button>
              ) : null}
            </div>
          </section>

          {route.kind === "course" || route.kind === "log-detail" ? (
            <section className="portal-shell__mode-nav">
              <header className="context-panel__header">
                <p className="eyebrow">Course Modes</p>
              </header>
              <div className="portal-mode-list">
                {[
                  ["overview", "Overview"],
                  ["lessons", "Lessons"],
                  ["builder", "Builder"],
                  ["logs", "Logs"],
                  ["analytics", "Analytics"],
                  ["roster", "Roster"],
                ].map(([mode, label]) => (
                  <button
                    key={mode}
                    className={
                      selectedMode === mode
                        ? "portal-mode-button portal-mode-button--active"
                        : "portal-mode-button"
                    }
                    onClick={() => navigate(
                      instructorPaths.course(
                        route.courseId,
                        mode as "overview" | "lessons" | "builder" | "logs" | "analytics" | "roster",
                      ),
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </section>
          ) : null}

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
              <dd>{route.kind === "home" ? "Course overview" : selectedMode}</dd>
              </div>
              {route.kind === "course" || route.kind === "log-detail" ? (
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
