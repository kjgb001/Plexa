import { useEffect, useState } from "react"

export type AppRoute =
  | { kind: "login" }
  | { kind: "auth-callback" }
  | { kind: "courses" }
  | { kind: "lessons"; courseId: string }
  | { kind: "chat"; courseId: string; lessonId: string; lessonVersion: string; sessionId: string | null }
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

export function parseRoute(pathname: string): AppRoute {
  if (pathname === "/" || pathname === "/login") {
    return { kind: "login" }
  }

  if (pathname === "/auth/callback") {
    return { kind: "auth-callback" }
  }

  if (pathname === "/app" || pathname === "/app/courses") {
    return { kind: "courses" }
  }

  const parts = pathname.split("/").filter(Boolean)

  if (
    parts.length === 3 &&
    parts[0] === "app" &&
    parts[1] === "courses"
  ) {
    return {
      kind: "lessons",
      courseId: decodeURIComponent(parts[2]),
    }
  }

  if (
    parts.length === 6 &&
    parts[0] === "app" &&
    parts[1] === "courses" &&
    parts[3] === "lessons"
  ) {
    return {
      kind: "chat",
      courseId: decodeURIComponent(parts[2]),
      lessonId: decodeURIComponent(parts[4]),
      lessonVersion: decodeURIComponent(parts[5]),
      sessionId: null,
    }
  }

  if (
    parts.length === 8 &&
    parts[0] === "app" &&
    parts[1] === "courses" &&
    parts[3] === "lessons" &&
    parts[6] === "sessions"
  ) {
    return {
      kind: "chat",
      courseId: decodeURIComponent(parts[2]),
      lessonId: decodeURIComponent(parts[4]),
      lessonVersion: decodeURIComponent(parts[5]),
      sessionId: decodeURIComponent(parts[7]),
    }
  }

  return { kind: "not-found" }
}
