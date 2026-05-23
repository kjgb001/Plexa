import { useEffect, useState } from "react"

export type StudentRoute =
  | { surface: "student"; kind: "courses" }
  | { surface: "student"; kind: "lessons"; courseId: string }
  | {
    surface: "student"
    kind: "chat"
    courseId: string
    lessonId: string
    lessonVersion: string
    sessionId: string | null
  }

export type InstructorRoute =
  | { surface: "instructor"; kind: "home" }
  | {
    surface: "instructor"
    kind: "course"
    courseId: string
    mode: "overview" | "lessons" | "builder" | "logs" | "analytics" | "roster"
  }
  | {
    surface: "instructor"
    kind: "log-detail"
    courseId: string
    sessionId: string
  }

export type AppRoute =
  | { kind: "login" }
  | { kind: "auth-callback" }
  | StudentRoute
  | InstructorRoute
  | { kind: "not-found" }

export function navigate(path: string, options?: { replace?: boolean }) {
  const nextPath = path.startsWith("/") ? path : `/${path}`

  if (options?.replace) {
    window.history.replaceState(null, "", nextPath)
  } else {
    window.history.pushState(null, "", nextPath)
  }

  window.dispatchEvent(new PopStateEvent("popstate"))
}

export function useCurrentPathname() {
  const [pathname, setPathname] = useState(() => window.location.pathname)

  useEffect(() => {
    function handleLocationChange() {
      setPathname(window.location.pathname)
    }

    window.addEventListener("popstate", handleLocationChange)

    return () => {
      window.removeEventListener("popstate", handleLocationChange)
    }
  }, [])

  return pathname
}

export const studentPaths = {
  courses: () => "/student/courses",
  lessons: (courseId: string) =>
    `/student/courses/${encodeURIComponent(courseId)}`,
  chat: (courseId: string, lessonId: string, lessonVersion: string) =>
    `/student/courses/${encodeURIComponent(courseId)}/lessons/${encodeURIComponent(lessonId)}/${encodeURIComponent(lessonVersion)}`,
  session: (courseId: string, lessonId: string, lessonVersion: string, sessionId: string) =>
    `/student/courses/${encodeURIComponent(courseId)}/lessons/${encodeURIComponent(lessonId)}/${encodeURIComponent(lessonVersion)}/sessions/${encodeURIComponent(sessionId)}`,
}

export const instructorPaths = {
  home: () => "/instructor",
  course: (
    courseId: string,
    mode: "overview" | "lessons" | "builder" | "logs" | "analytics" | "roster" = "overview",
  ) =>
    `/instructor/courses/${encodeURIComponent(courseId)}/${mode}`,
  logDetail: (courseId: string, sessionId: string) =>
    `/instructor/courses/${encodeURIComponent(courseId)}/logs/${encodeURIComponent(sessionId)}`,
}

function parseStudentRoute(parts: string[]): StudentRoute | null {
  if (parts.length === 2 && parts[0] === "student" && parts[1] === "courses") {
    return { surface: "student", kind: "courses" }
  }

  if (
    parts.length === 3 &&
    parts[0] === "student" &&
    parts[1] === "courses"
  ) {
    return {
      surface: "student",
      kind: "lessons",
      courseId: decodeURIComponent(parts[2]),
    }
  }

  if (
    parts.length === 6 &&
    parts[0] === "student" &&
    parts[1] === "courses" &&
    parts[3] === "lessons"
  ) {
    return {
      surface: "student",
      kind: "chat",
      courseId: decodeURIComponent(parts[2]),
      lessonId: decodeURIComponent(parts[4]),
      lessonVersion: decodeURIComponent(parts[5]),
      sessionId: null,
    }
  }

  if (
    parts.length === 8 &&
    parts[0] === "student" &&
    parts[1] === "courses" &&
    parts[3] === "lessons" &&
    parts[6] === "sessions"
  ) {
    return {
      surface: "student",
      kind: "chat",
      courseId: decodeURIComponent(parts[2]),
      lessonId: decodeURIComponent(parts[4]),
      lessonVersion: decodeURIComponent(parts[5]),
      sessionId: decodeURIComponent(parts[7]),
    }
  }

  return null
}

function parseLegacyStudentRoute(parts: string[]): StudentRoute | null {
  if (parts.length === 1 && parts[0] === "app") {
    return { surface: "student", kind: "courses" }
  }

  if (parts.length >= 2 && parts[0] === "app") {
    return parseStudentRoute(["student", ...parts.slice(1)])
  }

  return null
}

function parseInstructorRoute(parts: string[]): InstructorRoute | null {
  if (parts.length === 1 && parts[0] === "instructor") {
    return { surface: "instructor", kind: "home" }
  }

  if (
    parts.length === 3 &&
    parts[0] === "instructor" &&
    parts[1] === "courses"
  ) {
    return {
      surface: "instructor",
      kind: "course",
      courseId: decodeURIComponent(parts[2]),
      mode: "overview",
    }
  }

  if (
    parts.length === 4 &&
    parts[0] === "instructor" &&
    parts[1] === "courses"
  ) {
    const mode = parts[3]
    if (!["overview", "lessons", "builder", "logs", "analytics", "roster"].includes(mode)) {
      return null
    }

    return {
      surface: "instructor",
      kind: "course",
      courseId: decodeURIComponent(parts[2]),
      mode: mode as "overview" | "lessons" | "builder" | "logs" | "analytics" | "roster",
    }
  }

  if (
    parts.length === 5 &&
    parts[0] === "instructor" &&
    parts[1] === "courses" &&
    parts[3] === "logs"
  ) {
    return {
      surface: "instructor",
      kind: "log-detail",
      courseId: decodeURIComponent(parts[2]),
      sessionId: decodeURIComponent(parts[4]),
    }
  }

  return null
}

export function parseRoute(pathname: string): AppRoute {
  if (pathname === "/" || pathname === "/login") {
    return { kind: "login" }
  }

  if (pathname === "/auth/callback") {
    return { kind: "auth-callback" }
  }

  const parts = pathname.split("/").filter(Boolean)

  return (
    parseStudentRoute(parts)
    ?? parseLegacyStudentRoute(parts)
    ?? parseInstructorRoute(parts)
    ?? { kind: "not-found" }
  )
}
