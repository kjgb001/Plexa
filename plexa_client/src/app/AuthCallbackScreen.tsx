import { useEffect } from "react"
import { useAuth } from "../auth/useAuth"
import { navigate } from "./router"

export default function AuthCallbackScreen() {
  const { handleCallback } = useAuth()

  useEffect(() => {
    let active = true

    async function completeCallback() {
      try {
        await handleCallback()

        if (active) {
          navigate("/app/courses", { replace: true })
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
      <h1>Plexa</h1>
      <p>Completing sign-in...</p>
    </div>
  )
}
