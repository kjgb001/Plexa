let currentLessonId: string | null = null
let currentLessonVersion: string | null = null

export function setCurrentLesson(LessonId: string, LessonVersion: string) {
  currentLessonId = LessonId
  currentLessonVersion = LessonVersion
}

export function getCurrentLesson() {
  if (!currentLessonId) { throw new Error("No lesson selected") } 
  else if (!currentLessonVersion) {
    throw new Error(`Lesson version missing for: ${currentLessonId}`)
  }

  return {lessonId: currentLessonId, lessonVersion: currentLessonVersion}
}

export function clearCurrentLesson() {
  currentLessonId = null
  currentLessonVersion = null
}