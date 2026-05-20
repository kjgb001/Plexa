import { navigate, instructorPaths, type InstructorRoute } from "../app/router"
import { InstructorShell } from "./InstructorShell"
import { InstructorCourseScreen } from "./screens/InstructorCourseScreen"
import { InstructorHomeScreen } from "./screens/InstructorHomeScreen"

export function InstructorApp({
  route,
  userId,
  onLogout,
}: {
  route: InstructorRoute
  userId: string | null
  onLogout(): Promise<void>
}) {
  const content = route.kind === "home" ? (
    <InstructorHomeScreen
      onOpenCourse={(courseId) => navigate(instructorPaths.course(courseId, "overview"))}
    />
  ) : (
    <InstructorCourseScreen courseId={route.courseId} mode={route.mode} />
  )

  return (
    <InstructorShell route={route} userId={userId} onLogout={onLogout}>
      {content}
    </InstructorShell>
  )
}
