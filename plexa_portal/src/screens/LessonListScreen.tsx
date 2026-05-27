import { useEffect, useState, type KeyboardEvent } from "react"
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

  function handleLessonCardKeyDown(
    event: KeyboardEvent<HTMLElement>,
    lesson: Lesson,
  ) {
    if (event.key !== "Enter" && event.key !== " ") {
      return
    }

    event.preventDefault()
    onSelectLesson(lesson.lesson_id, lesson.version)
  }

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
                <article
                  className={
                    lesson.is_pinned_now
                      ? "catalog-entry catalog-entry--lesson catalog-entry--pinned"
                      : "catalog-entry catalog-entry--lesson"
                  }
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectLesson(lesson.lesson_id, lesson.version)}
                  onKeyDown={(event) => handleLessonCardKeyDown(event, lesson)}
                >
                  <header className="catalog-entry__header">
                    <p className="catalog-entry__index">{String(index + 1).padStart(2, "0")}</p>
                    <div>
                      <p className="catalog-entry__eyebrow">Lesson</p>
                      <h3 className="catalog-entry__title-with-icon">
                        {lesson.is_pinned_now ? (
                          <span className="pin-indicator" aria-label="Pinned lesson" title="Pinned lesson">
                            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                              <path d="M15 3c.55 0 1 .45 1 1v2.17l2.41 2.42c.38.37.59.88.59 1.41V12c0 .55-.45 1-1 1h-5v7l-1 1-1-1v-7H6c-.55 0-1-.45-1-1V10c0-.53.21-1.04.59-1.41L8 6.17V4c0-.55.45-1 1-1h6Z" fill="currentColor" />
                            </svg>
                          </span>
                        ) : null}
                        <span>{lesson.title}</span>
                      </h3>
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
                      <dd>{lesson.difficulty ?? "Not specified"}</dd>
                    </div>
                    <div>
                      <dt>Duration</dt>
                      <dd>{lesson.approximate_time ?? "Not specified"}</dd>
                    </div>
                  </dl>
                  <footer className="catalog-entry__footer">
                    <p>{lesson.author ?? "Unknown author"}</p>
                    <span className="catalog-entry__action" aria-hidden="true">
                      Open lesson
                    </span>
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
