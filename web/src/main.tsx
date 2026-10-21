import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import { AuthProvider, useAuth } from './lib/auth'
import { AdminPage } from './pages/AdminPage'
import { AuthPage } from './pages/AuthPage'
import { PlannerPage } from './pages/PlannerPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'

function App() {
  const { session, loading, setupError, recovering } = useAuth()

  if (loading) return <div className="center muted">Loading…</div>
  if (setupError) {
    return (
      <div className="center">
        <div className="auth-card">
          <h1>Setup needed</h1>
          <p className="alert error">{setupError}</p>
          <p className="muted small">See “Run the website locally” in the README.</p>
        </div>
      </div>
    )
  }
  if (recovering) return <ResetPasswordPage />
  if (!session) return <AuthPage />

  return (
    <Routes>
      <Route path="/" element={<PlannerPage />} />
      <Route path="/admin" element={<AdminPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
