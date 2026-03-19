import { useEffect, useState } from "react"
import { useApis } from "../api"
import { NotFoundError } from "../api/errors"
import type { Lesson } from "../api/interfaces"

interface Props {
  courseId: string
  onSelectLesson: (lessonId: string, lessonVersion:string) => void
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
              "This course is visible, but its lessons are not available to your account yet. You may need enrollment approval."
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
    <section className="screen-card">
      <div className="screen-card__header">
        <div>
          <p className="eyebrow">Lesson Selection</p>
          <h1>Pick a lesson workspace</h1>
          <p>
            Each lesson opens as its own focused chat context. You can return to
            prior sessions later, but the lesson remains the stable frame.
          </p>
        </div>
      </div>

      {loading ? <p>Loading lesson menu...</p> : null}

      {!loading && loadError ? (
        <div className="empty-panel">
          <p>{loadError}</p>
          <div className="screen-card__actions">
            <button
              className="primary-button"
              onClick={() => void handleEnrollmentRequest()}
              disabled={requestingEnrollment}
            >
              {requestingEnrollment ? "Requesting..." : "Request Enrollment"}
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
          </div>
        </div>
      ) : null}

      {!loading && lessons.length === 0 ? (
        <div className="empty-panel">
          This course has no visible lessons yet.
        </div>
      ) : null}

      <div className="rail__list">
        {lessons.map((lesson) => (
          <button
            key={`${lesson.lesson_id}:${lesson.version}`}
            className="rail-card"
            onClick={() => onSelectLesson(lesson.lesson_id, lesson.version)}
          >
            <span className="rail-card__title">{lesson.title}</span>
            <span className="rail-card__meta">
              {lesson.learning_objective ?? lesson.difficulty ?? "Open lesson"}
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}
