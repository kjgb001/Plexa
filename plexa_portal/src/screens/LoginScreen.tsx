import { useState } from "react"
import type { AuthMode } from "../auth/types"

export default function LoginScreen({
  mode,
  onLogin,
}: {
  mode: AuthMode
  onLogin: (options: { userId?: string; portal: "student" | "instructor" }) => Promise<void>
}) {
  const [selectedPortal, setSelectedPortal] = useState<"student" | "instructor" | null>(null)

  async function handleLogin(portal: "student" | "instructor") {
    if (mode === "dev") {
      const userId = window.prompt("Enter dev user ID")
      if (!userId?.trim()) return
      await onLogin({ userId: userId.trim(), portal })
      return
    }
    await onLogin({ portal })
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa Portal</h1>
      {selectedPortal === null ? (
        <>
          <p>Select a portal.</p>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button onClick={() => setSelectedPortal("student")}>Student portal</button>
            <button onClick={() => setSelectedPortal("instructor")}>Instructor portal</button>
          </div>
        </>
      ) : (
        <>
          <p>
            {mode === "dev"
              ? `Continue to the ${selectedPortal} portal.`
              : `Continue to your configured identity provider for ${selectedPortal} portal access.`}
          </p>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button onClick={() => void handleLogin(selectedPortal)}>Login</button>
            <button onClick={() => setSelectedPortal(null)}>Back</button>
          </div>
        </>
      )}
    </div>
  )
}
