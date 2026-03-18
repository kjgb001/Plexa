import { useEffect, useMemo, useState, type ReactNode } from "react"
import { navigate, type AppRoute } from "./router"
import { useApis } from "../api"
import type { Course, Lesson } from "../api/interfaces"

interface StudentShellProps {
  route: Exclude<AppRoute, { kind: "login" | "auth-callback" | "not-found" }>
  userId: string | null
  onLogout(): Promise<void>
  children: ReactNode
}

export default function StudentShell({
  route,
  userId,
  onLogout,
  children,
}: StudentShellProps) {
  const { courseApi } = useApis()
  const [courses, setCourses] = useState<Course[]>([])
  const [lessons, setLessons] = useState<Lesson[]>([])

  const selectedCourseId =
    route.kind === "courses" ? null : route.courseId

  const selectedLessonId =
    route.kind === "chat" ? route.lessonId : null

  const selectedLessonVersion =
    route.kind === "chat" ? route.lessonVersion : null

  useEffect(() => {
    let active = true

    async function loadCourses() {
      try {
        const result = await courseApi.listDiscoverable()

        if (active) {
          setCourses(result.courses)
        }
      } catch {
        if (active) {
          setCourses([])
        }
      }
    }

    void loadCourses()

    return () => {
      active = false
    }
  }, [courseApi])

  useEffect(() => {
    let active = true

    async function loadLessons() {
      if (!selectedCourseId) {
        setLessons([])
        return
      }

      try {
        const result = await courseApi.listLessons(selectedCourseId)

        if (active) {
          setLessons(result.lessons)
        }
      } catch {
        if (active) {
          setLessons([])
        }
      }
    }

    void loadLessons()

    return () => {
      active = false
    }
  }, [courseApi, selectedCourseId])

  const selectedCourse = useMemo(
    () => courses.find((course) => course.course_id === selectedCourseId) ?? null,
    [courses, selectedCourseId],
  )

  const selectedLesson = useMemo(
    () =>
      lessons.find(
        (lesson) =>
          lesson.lesson_id === selectedLessonId &&
          lesson.version === selectedLessonVersion,
      ) ?? null,
    [lessons, selectedLessonId, selectedLessonVersion],
  )

  return (
    <div className="app-shell">
      <aside className="app-shell__rail">
        <div className="rail__brand">
          <div>
            <p className="eyebrow">Student Workspace</p>
            <h1>Plexa</h1>
          </div>
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

        <section className="rail__section">
          <div className="rail__section-header">
            <h2>Courses</h2>
            <button
              className="ghost-button"
              onClick={() => navigate("/app/courses")}
            >
              Browse
            </button>
          </div>

          <div className="rail__list">
            {courses.map((course) => {
              const isActive = course.course_id === selectedCourseId

              return (
                <button
                  key={course.course_id}
                  className={isActive ? "rail-card rail-card--active" : "rail-card"}
                  onClick={() => navigate(`/app/courses/${encodeURIComponent(course.course_id)}`)}
                >
                  <span className="rail-card__title">{course.title}</span>
                  {course.description ? (
                    <span className="rail-card__meta">{course.description}</span>
                  ) : null}
                </button>
              )
            })}
          </div>
        </section>

        <section className="rail__section rail__section--flex">
          <div className="rail__section-header">
            <h2>Lessons</h2>
            {selectedCourse ? (
              <span className="section-chip">{selectedCourse.course_id}</span>
            ) : null}
          </div>

          {selectedCourseId ? (
            <div className="rail__list">
              {lessons.map((lesson) => {
                const isActive =
                  lesson.lesson_id === selectedLessonId &&
                  lesson.version === selectedLessonVersion

                return (
                  <button
                    key={`${lesson.lesson_id}:${lesson.version}`}
                    className={isActive ? "rail-card rail-card--active" : "rail-card"}
                    onClick={() =>
                      navigate(
                        `/app/courses/${encodeURIComponent(selectedCourseId)}/lessons/${encodeURIComponent(lesson.lesson_id)}/${encodeURIComponent(lesson.version)}`,
                      )
                    }
                  >
                    <span className="rail-card__title">{lesson.title}</span>
                    <span className="rail-card__meta">
                      {lesson.difficulty ?? "Open level"}
                    </span>
                  </button>
                )
              })}
            </div>
          ) : (
            <div className="empty-panel">
              Choose a course to view lesson options.
            </div>
          )}
        </section>
      </aside>

      <div className="app-shell__main">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Active Context</p>
            <h2>
              {selectedLesson?.title ??
                selectedCourse?.title ??
                "Course and lesson selection"}
            </h2>
          </div>

          <div className="workspace-header__meta">
            <span className="section-chip">{userId ?? "Unknown user"}</span>
            {selectedCourse ? (
              <span className="section-chip">{selectedCourse.course_id}</span>
            ) : null}
            {selectedLesson ? (
              <span className="section-chip">v{selectedLesson.version}</span>
            ) : null}
          </div>
        </header>

        <main className="workspace-main">{children}</main>
      </div>

      <aside className="app-shell__context">
        <div className="context-card">
          <p className="eyebrow">Lesson Context</p>
          {selectedLesson ? (
            <>
              <h3>{selectedLesson.title}</h3>
              <dl className="context-list">
                <div>
                  <dt>Author</dt>
                  <dd>{selectedLesson.author ?? "Unknown"}</dd>
                </div>
                <div>
                  <dt>Difficulty</dt>
                  <dd>{selectedLesson.difficulty ?? "Not specified"}</dd>
                </div>
                <div>
                  <dt>Approx. Time</dt>
                  <dd>{selectedLesson.approximate_time ?? "Flexible"}</dd>
                </div>
                <div>
                  <dt>Objective</dt>
                  <dd>{selectedLesson.learning_objective ?? "Objective unavailable"}</dd>
                </div>
                <div>
                  <dt>Behavioral Focus</dt>
                  <dd>{selectedLesson.behavioral_focus ?? "Not specified"}</dd>
                </div>
              </dl>

              {selectedLesson.tags?.length ? (
                <div className="tag-row">
                  {selectedLesson.tags.map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <>
              <h3>Context will live here</h3>
              <p>
                Select a lesson to keep its goals, framing, and constraints visible
                while students work in chat.
              </p>
            </>
          )}
        </div>

        <div className="context-card context-card--muted">
          <p className="eyebrow">Design Direction</p>
          <p>
            The shell keeps navigation stable, chat central, and course context
            persistent so the later UI pass can feel familiar without turning into
            a generic chatbot clone.
          </p>
        </div>
      </aside>
    </div>
  )
}
