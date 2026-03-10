let currentCourseId: string | null = null

export function setCurrentCourse(courseId: string) {
  currentCourseId = courseId
}

export function getCurrentCourse() {
  if (!currentCourseId) {
    throw new Error("No course selected")
  }

  return currentCourseId
}

export function clearCurrentCourse() {
  currentCourseId = null
}