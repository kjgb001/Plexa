import { useContext } from "react"
import { ApiContext } from "./ApiContext"

export function useApis() {
  const context = useContext(ApiContext)

  if (!context) {
    throw new Error("useApis must be used within ApiProvider")
  }

  return context
}
