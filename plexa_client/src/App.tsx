import { useState } from "react"
import LoginScreen from "./screens/LoginScreen"
import CourseListScreen from "./screens/CourseListScreen"
import ChatScreen from "./screens/ChatScreen"

export default function App() {
  const [loggedIn, setLoggedIn] = useState(
    !!localStorage.getItem("plexa_user")
  )

  if (!loggedIn) {
    return <LoginScreen onLogin={() => setLoggedIn(true)} />
  }

  return <ChatScreen />
}