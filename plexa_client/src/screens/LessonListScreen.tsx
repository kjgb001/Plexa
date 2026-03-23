import { useEffect, useState } from "react"
import { useApis } from "../api"
import { NotFoundError } from "../api/errors"
import type { Lesson } from "../api/interfaces"

interface Props {
  courseId: string
  onSelectLesson: (lessonId: string, lessonVersion: string) => void
}

export default function LessonListScreen({ courseId, onSelectLesson }: Props) {
  const { courseApi } = useApis()
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [requestingEnrollment, setRequestingEnrollment] = useState(false)
  const [enrollmentStatus, setEnrollmentStatus] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadLessons() {
      if (active) {
        setLoading(true)
        setLoadError(null)
      }

      try {
        const result = await courseApi.listLessons(courseId)
        if (active) {
          setLessons(result.lessons ?? [])
        }
      } catch (err) {
        if (active) {
          setLessons([])
          console.error("Failed to load lessons", err)

          if (err instanceof NotFoundError) {
            setLoadError(
              "This course is visible, but its lessons are not available to your account yet. You may need enrollment approval.",
            )
          } else {
            setLoadError("Failed to load lessons for this course.")
          }
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadLessons()

    return () => {
      active = false
    }
  }, [courseApi, courseId])

  async function handleEnrollmentRequest() {
    setRequestingEnrollment(true)
    setEnrollmentStatus(null)

    try {
      const result = await courseApi.requestEnrollment(courseId)
      setEnrollmentStatus(result.status)
    } catch (err) {
      console.error("Enrollment request failed", err)
      setEnrollmentStatus("error")
    } finally {
      setRequestingEnrollment(false)
    }
  }

  return (
    <section className="catalog-stage catalog-stage--lessons" aria-labelledby="lesson-stage-title">
      <header className="catalog-stage__hero">
        <p className="eyebrow">Lesson Selection</p>
        <h1 id="lesson-stage-title">Pick a lesson workspace</h1>
        <p className="catalog-stage__summary">
          Each lesson is an instructional frame with its own objectives,
          behavioral expectations, and session history.
        </p>
      </header>

      <section className="catalog-stage__body" aria-label="Lesson browser">
        <aside className="catalog-stage__brief">
          <h2>What carries into every session</h2>
          <p>
            The lesson objective stays persistent while sessions let students
            iterate, restart, and compare different conversational attempts.
          </p>

          {loading === false && loadError ? (
            <section className="notice-panel" aria-label="Enrollment notice">
              <h3>Access needed</h3>
              <p>{loadError}</p>
              <footer className="notice-panel__actions">
                <button
                  className="primary-button"
                  onClick={() => void handleEnrollmentRequest()}
                  disabled={requestingEnrollment}
                >
                  {requestingEnrollment ? "Requesting..." : "Request enrollment"}
                </button>
                {enrollmentStatus ? (
                  <span className="section-chip">
                    {enrollmentStatus === "pending"
                      ? "Enrollment requested"
                      : enrollmentStatus === "already_enrolled"
                        ? "Already enrolled"
                        : "Request failed"}
                  </span>
                ) : null}
              </footer>
            </section>
          ) : null}
        </aside>

        <section className="catalog-stage__rail" aria-label="Available lessons">
          <header className="catalog-stage__section-header">
            <h2>Available Lessons</h2>
            <p>Choose the lesson that will anchor the chat workspace.</p>
          </header>

          {loading ? <p className="status-note">Loading lesson menu...</p> : null}

          {loading === false && loadError === null && lessons.length === 0 ? (
            <p className="empty-panel" role="status">
              This course has no visible lessons yet.
            </p>
          ) : null}

          <ol className="catalog-list catalog-list--compact">
            {lessons.map((lesson, index) => (
              <li key={lesson.lesson_id + ":" + lesson.version}>
                <article className="catalog-entry catalog-entry--lesson">
                  <header className="catalog-entry__header">
                    <p className="catalog-entry__index">{String(index + 1).padStart(2, "0")}</p>
                    <div>
                      <p className="catalog-entry__eyebrow">Lesson</p>
                      <h3>{lesson.title}</h3>
                    </div>
                    <span className="section-chip">v{lesson.version}</span>
                  </header>
                  <dl className="catalog-entry__details">
                    <div>
                      <dt>Objective</dt>
                      <dd>{lesson.learning_objective ?? "Open lesson"}</dd>
                    </div>
                    <div>
                      <dt>Difficulty</dt>
                      <dd>{lesson.difficulty ?? "Flexible"}</dd>
                    </div>
                    <div>
                      <dt>Duration</dt>
                      <dd>{lesson.approximate_time ?? "Flexible pace"}</dd>
                    </div>
                  </dl>
                  <footer className="catalog-entry__footer">
                    <p>{lesson.author ?? "Unknown author"}</p>
                    <button
                      className="catalog-entry__action"
                      onClick={() => onSelectLesson(lesson.lesson_id, lesson.version)}
                    >
                      Open lesson
                    </button>
                  </footer>
                </article>
              </li>
            ))}
          </ol>
        </section>
      </section>
    </section>
  )
}
