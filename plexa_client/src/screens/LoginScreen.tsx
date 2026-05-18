import { useState } from "react"
import type { AuthMode } from "../auth/types"

export default function LoginScreen({
  mode,
  onLogin,
}: {
  mode: AuthMode
  onLogin: (userId?: string) => Promise<void>
}) {
  const [userId, setUserId] = useState("")

  async function handleLogin() {
    if (mode === "dev") {
      if (!userId.trim()) return
      await onLogin(userId.trim())
      return
    }
    await onLogin()
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa</h1>
      {mode === "dev" ? (
        <>
          <p>Enter a dev user ID:</p>

          <input
            value={userId}
            onChange={e => setUserId(e.target.value)}
            placeholder="student1"
          />

          <button onClick={() => void handleLogin()}>Login</button>
        </>
      ) : (
        <>
          <p>Sign in with your configured identity provider.</p>
          <button onClick={() => void handleLogin()}>Sign in</button>
        </>
      )}
    </div>
  )
}
