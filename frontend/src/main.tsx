import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { Parameters } from './pages/Parameters'
import { consumeAuthHandoff } from './lib/auth'

/** `#parameters` opens the admin screen; writes are still gated by FM. */
const isParameterAdmin = () => window.location.hash.replace(/^#/, '') === 'parameters'

void consumeAuthHandoff().finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>{isParameterAdmin() ? <Parameters /> : <App />}</StrictMode>,
  )
})
