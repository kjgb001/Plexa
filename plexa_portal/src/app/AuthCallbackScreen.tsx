import { useEffect } from "react"
import { useAuth } from "../auth/useAuth"
import { navigate, studentPaths } from "./router"

export default function AuthCallbackScreen() {
  const { handleCallback } = useAuth()

  useEffect(() => {
    let active = true

    async function completeCallback() {
      try {
        await handleCallback()

        if (active) {
          navigate(studentPaths.courses(), { replace: true })
        }
      } catch {
        if (active) {
          navigate("/login", { replace: true })
        }
      }
    }

    void completeCallback()

    return () => {
      active = false
    }
  }, [handleCallback])

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa Portal</h1>
      <p>Completing sign-in...</p>
    </div>
  )
}
