import { useEffect, useRef, useState } from 'react'
import './index.css'

// ── Types ────────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  timestamp: number
}

interface Status {
  detections: string[]
  motor_connected: boolean
  cam_connected: boolean
  voice_status: 'idle' | 'listening' | 'processing'
  depth_enabled: boolean
  chat_messages: ChatMessage[]
}

const DEFAULT_STATUS: Status = {
  detections: [],
  motor_connected: false,
  cam_connected: false,
  voice_status: 'idle',
  depth_enabled: true,
  chat_messages: [],
}

// ── Small reusable components ─────────────────────────────────────────────────

function Dot({ on, color = 'var(--green)' }: { on: boolean; color?: string }) {
  return (
    <div style={{
      width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
      background: on ? color : 'var(--red)',
      boxShadow: on ? `0 0 6px ${color}` : '0 0 6px var(--red)',
    }} />
  )
}

function StatusPill({ on, label }: { on: boolean; label: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '5px 10px', borderRadius: 20,
      background: 'var(--card)', border: '1px solid var(--border)',
      fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
      color: on ? '#e2e8f0' : 'var(--muted)',
    }}>
      <Dot on={on} />
      {label}
    </div>
  )
}

function DetectionBadge({ text }: { text: string }) {
  const parts = text.match(/^(.+?)\s+(left|center|right)$/i)
  const label = parts ? parts[1] : text
  const dir = (parts ? parts[2] : '').toLowerCase()
  const dirColors: Record<string, string> = {
    left: 'var(--blue)', center: 'var(--green)', right: 'var(--yellow)',
  }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 8px', borderRadius: 5,
      background: '#161b24', border: '1px solid var(--border)',
      fontSize: 11, marginRight: 5, marginBottom: 5,
    }}>
      <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{label}</span>
      {dir && (
        <span style={{ color: dirColors[dir] || 'var(--muted)', fontWeight: 700, textTransform: 'uppercase' }}>
          {dir}
        </span>
      )}
    </span>
  )
}

// ── Chat window ───────────────────────────────────────────────────────────────

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  const time = new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 12,
    }}>
      <div style={{
        fontSize: 10, color: 'var(--muted)', marginBottom: 3,
        textTransform: 'uppercase', letterSpacing: 1,
      }}>
        {isUser ? 'You' : 'Echo'} · {time}
      </div>
      <div style={{
        maxWidth: '80%', padding: '10px 14px', borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        background: isUser ? '#1a3a5c' : '#0f2a1f',
        border: `1px solid ${isUser ? '#2a5a8c' : '#1a4a2f'}`,
        color: isUser ? 'var(--blue)' : 'var(--green)',
        fontSize: 13, lineHeight: 1.5, fontWeight: 500,
      }}>
        {msg.text}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 12 }}>
      <div style={{
        padding: '10px 16px', borderRadius: '16px 16px 16px 4px',
        background: '#0f2a1f', border: '1px solid #1a4a2f',
        display: 'flex', gap: 5, alignItems: 'center',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 6, height: 6, borderRadius: '50%', background: 'var(--green)',
            animation: `bounce 1.2s ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}

function ChatWindow({ messages, voiceStatus }: { messages: ChatMessage[]; voiceStatus: Status['voice_status'] }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, voiceStatus])

  const voiceColors = { idle: 'var(--muted)', listening: 'var(--green)', processing: 'var(--yellow)' }
  const voiceLabels = { idle: "Say 'Hey Echo' to activate", listening: 'Listening...', processing: 'Echo is thinking...' }

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12,
      overflow: 'hidden', minHeight: 0,
    }}>
      {/* Chat header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 10,
        fontSize: 10, fontWeight: 700, letterSpacing: 2, color: 'var(--muted)', textTransform: 'uppercase',
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: voiceColors[voiceStatus],
          boxShadow: voiceStatus !== 'idle' ? `0 0 8px ${voiceColors[voiceStatus]}` : 'none',
          animation: voiceStatus === 'listening' ? 'pulse 1s infinite' : 'none',
        }} />
        Echo Voice · {voiceLabels[voiceStatus]}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', minHeight: 0 }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--muted)', marginTop: 40 }}>
            <div style={{ fontSize: 28, marginBottom: 10 }}>🎙</div>
            <div style={{ fontSize: 12, letterSpacing: 1 }}>Say "Hey Echo" to start</div>
          </div>
        ) : (
          messages.map((msg, i) => <ChatBubble key={i} msg={msg} />)
        )}
        {voiceStatus === 'processing' && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Main app ──────────────────────────────────────────────────────────────────

export default function App() {
  const [status, setStatus] = useState<Status>(DEFAULT_STATUS)
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    function connect() {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${window.location.host}/ws`)
      wsRef.current = ws
      ws.onopen = () => setWsConnected(true)
      ws.onclose = () => { setWsConnected(false); setTimeout(connect, 2000) }
      ws.onmessage = (e) => { try { setStatus(JSON.parse(e.data)) } catch {} }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
        padding: '12px 24px', borderBottom: '1px solid var(--border)', background: 'var(--card)',
      }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: 3, color: 'var(--green)', textTransform: 'uppercase' }}>
          Echo Vest
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: status.cam_connected ? 'var(--green)' : 'var(--red)',
            animation: status.cam_connected ? 'pulse 2s infinite' : 'none',
          }} />
          <span style={{ fontSize: 11, color: status.cam_connected ? 'var(--green)' : 'var(--red)', fontWeight: 700, letterSpacing: 1 }}>
            {status.cam_connected ? 'LIVE' : 'NO SIGNAL'}
          </span>
        </div>

        {/* Status pills in header */}
        <div style={{ display: 'flex', gap: 8, marginLeft: 16, flexWrap: 'wrap' }}>
          <StatusPill on={status.cam_connected} label="ESP32-CAM" />
          <StatusPill on={status.motor_connected} label="Motor ESP32" />
          <StatusPill on label="YOLOv8n" />
          <StatusPill on label="MiDaS" />
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Dot on={wsConnected} color="var(--blue)" />
          <span style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1 }}>
            {wsConnected ? 'DASHBOARD CONNECTED' : 'CONNECTING...'}
          </span>
        </div>
      </header>

      {/* Two-column canvas */}
      <main style={{
        flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr',
        gap: 16, padding: 16, minHeight: 0, overflow: 'hidden',
      }}>

        {/* LEFT — camera feed + depth + detections */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}>
          {/* Camera */}
          <div style={{
            flex: 1, background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 12, overflow: 'hidden', position: 'relative',
            display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0,
          }}>
            {status.cam_connected ? (
              <img src="/stream" alt="YOLO stream"
                style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
            ) : (
              <div style={{ textAlign: 'center', color: 'var(--muted)' }}>
                <div style={{ fontSize: 36, marginBottom: 10 }}>📷</div>
                <div style={{ fontSize: 12, letterSpacing: 1 }}>WAITING FOR CAMERA</div>
              </div>
            )}
            <div style={{
              position: 'absolute', top: 10, left: 10,
              background: 'rgba(0,0,0,0.75)', borderRadius: 6,
              padding: '3px 9px', fontSize: 10, letterSpacing: 1, color: 'var(--green)', fontWeight: 700,
            }}>
              YOLO + DEPTH
            </div>
          </div>

          {/* Depth map */}
          {status.depth_enabled && (
            <div style={{
              height: 160, background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 12, overflow: 'hidden', position: 'relative', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {status.cam_connected ? (
                <img src="/depth" alt="Depth map"
                  style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
              ) : (
                <div style={{ color: 'var(--muted)', fontSize: 12, letterSpacing: 1 }}>DEPTH MAP OFFLINE</div>
              )}
              <div style={{
                position: 'absolute', top: 8, left: 10,
                background: 'rgba(0,0,0,0.75)', borderRadius: 6,
                padding: '3px 8px', fontSize: 10, letterSpacing: 1, color: 'var(--yellow)', fontWeight: 700,
              }}>
                MiDaS DEPTH
              </div>
            </div>
          )}

          {/* Detections */}
          <div style={{
            flexShrink: 0, background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 12, padding: '10px 14px',
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              Detections ({status.detections.length})
            </div>
            {status.detections.length === 0 ? (
              <span style={{ fontSize: 12, color: 'var(--muted)', fontStyle: 'italic' }}>No obstacles detected</span>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                {status.detections.map((d, i) => <DetectionBadge key={i} text={d} />)}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT — chat window */}
        <ChatWindow messages={status.chat_messages} voiceStatus={status.voice_status} />
      </main>

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        @keyframes bounce { 0%, 80%, 100% { transform: translateY(0); } 40% { transform: translateY(-6px); } }
      `}</style>
    </div>
  )
}
