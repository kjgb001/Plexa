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
      <header className="catalog-stage__hero catalog-stage__hero--sticky">
        <p className="eyebrow">Lesson Selection</p>
        <h1 id="lesson-stage-title">Available Lessons</h1>
      </header>

      <section className="catalog-stage__body catalog-stage__body--lessons" aria-label="Lesson browser">
        <section className="catalog-stage__rail catalog-stage__rail--scroll" aria-label="Available lessons">
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
