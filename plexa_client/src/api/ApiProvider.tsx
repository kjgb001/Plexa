import {
  useState,
  type ReactNode,
} from "react"
import { useAuth } from "../auth/useAuth"
import { HttpClient } from "./http"
import { CourseApi } from "./courses"
import { SessionApi } from "./sessions"
import { ApiContext, type ApiContextValue } from "./ApiContext"

export function ApiProvider({ children }: { children: ReactNode }) {
  const { authService } = useAuth()
  const [http] = useState(() => new HttpClient(() => authService.getAuthHeaders()))
  const [apis] = useState<ApiContextValue>(() => ({
    courseApi: new CourseApi(http),
    sessionApi: new SessionApi(http),
  }))

  return (
    <ApiContext.Provider value={apis}>
      {children}
    </ApiContext.Provider>
  )
}
