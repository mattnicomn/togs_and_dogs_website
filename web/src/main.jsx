import React from 'react'
import ReactDOM from 'react-dom/client'
import { Buffer } from 'buffer'
import App from './App'
import './index.css'

if (!window.global) {
  window.global = window
}

if (!window.Buffer) {
  window.Buffer = Buffer
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
