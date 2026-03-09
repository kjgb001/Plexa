import { useState } from "react"
import { authService } from "../api"

export default function LoginScreen({ onLogin }: { onLogin: () => void }) {
  const [userId, setUserId] = useState("")

  function handleLogin() {
    if (!userId.trim()) return
    authService.login(userId)
    onLogin()
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Plexa</h1>
      <p>Enter a dev user ID:</p>

      <input
        value={userId}
        onChange={e => setUserId(e.target.value)}
        placeholder="student1"
      />

      <button onClick={handleLogin}>Login</button>
    </div>
  )
}