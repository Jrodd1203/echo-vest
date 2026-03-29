import { useEffect, useRef, useState } from 'react'
import './index.css'

// ── Types ─────────────────────────────────────────────────────────────────────

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

const EMPTY: Status = {
  detections: [], motor_connected: false, cam_connected: false,
  voice_status: 'idle', depth_enabled: true, chat_messages: [],
}

// ── Shared style constants ────────────────────────────────────────────────────

const mono: React.CSSProperties = { fontFamily: 'var(--font-mono)' }
const sans: React.CSSProperties = { fontFamily: 'var(--font-sans)' }

const SECTION: React.CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius)',
}

const LABEL: React.CSSProperties = {
  ...mono,
  fontSize: 9,
  fontWeight: 600,
  letterSpacing: '0.12em',
  textTransform: 'uppercase' as const,
  color: 'var(--text-muted)',
}

// ── Status indicator ──────────────────────────────────────────────────────────

interface IndicatorProps {
  live: boolean
  label: string
  liveLabel?: string
  offLabel?: string
  color?: string
}

function Indicator({ live, label, liveLabel = 'ONLINE', offLabel = 'OFFLINE', color = 'var(--ok)' }: IndicatorProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <div style={{
        ...mono,
        fontSize: 9,
        letterSpacing: '0.1em',
        color: 'var(--text-dim)',
      }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <div style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: live ? color : 'var(--text-dim)',
          animation: live ? 'status-live 2.4s ease-in-out infinite' : 'none',
          flexShrink: 0,
        }} />
        <span style={{
          ...mono,
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: '0.08em',
          color: live ? color : 'var(--text-dim)',
          transition: 'color 0.3s',
        }}>
          {live ? liveLabel : offLabel}
        </span>
      </div>
    </div>
  )
}

// ── System bar ────────────────────────────────────────────────────────────────

interface SystemBarProps {
  status: Status
  active: boolean
  wsConnected: boolean
  onStart: () => void
  onStop: () => void
}

function SystemBar({ status, active, wsConnected, onStart, onStop }: SystemBarProps) {
  const divider: React.CSSProperties = {
    width: 1, height: 18,
    background: 'var(--border-strong)',
    flexShrink: 0,
  }

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      gap: 20,
      height: 48,
      padding: '0 20px',
      borderBottom: '1px solid var(--border)',
      background: 'var(--surface)',
      flexShrink: 0,
    }}>
      {/* Wordmark */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <div style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: active ? 'var(--accent)' : 'var(--text-dim)',
          animation: active ? 'status-live 1.8s ease-in-out infinite' : 'none',
        }} />
        <span style={{
          ...mono,
          fontSize: 13,
          fontWeight: 600,
          letterSpacing: '0.18em',
          color: 'var(--text)',
        }}>
          ECHO VEST
        </span>
      </div>

      <div style={divider} />

      {/* System status row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <Indicator live={status.cam_connected} label="CAM" liveLabel="LIVE" offLabel="NO SIGNAL" color="var(--ok)" />
        <Indicator live={status.motor_connected} label="HAPTICS" color="var(--ok)" />
        <Indicator live={active} label="YOLO" liveLabel="RUNNING" color="var(--accent)" />
        <Indicator live={active && status.depth_enabled} label="DEPTH" liveLabel="ACTIVE" color="var(--accent)" />
      </div>

      <div style={divider} />

      <Indicator
        live={wsConnected}
        label="DASHBOARD"
        liveLabel="CONNECTED"
        color="var(--accent)"
      />

      {/* Session control */}
      <div style={{ marginLeft: 'auto' }}>
        <button
          onClick={active ? onStop : onStart}
          style={{
            ...mono,
            padding: '0 16px',
            height: 30,
            background: active ? 'var(--danger-dim)' : 'var(--accent-dim)',
            border: `1px solid ${active ? 'rgba(255,63,63,0.4)' : 'rgba(0,212,255,0.35)'}`,
            borderRadius: 'var(--radius)',
            color: active ? 'var(--danger)' : 'var(--accent)',
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: '0.12em',
            cursor: 'pointer',
            transition: 'background 0.2s, border-color 0.2s',
            whiteSpace: 'nowrap' as const,
          }}
        >
          {active ? 'STOP SESSION' : 'START SESSION'}
        </button>
      </div>
    </header>
  )
}

// ── Camera feed ───────────────────────────────────────────────────────────────

function CameraFeed({ active, camConnected }: { active: boolean; camConnected: boolean }) {
  const showFeed = active && camConnected

  return (
    <div style={{
      ...SECTION,
      flex: 1,
      overflow: 'hidden',
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 0,
    }}>
      {showFeed ? (
        <img
          src="/stream"
          alt="YOLO annotated feed"
          style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
        />
      ) : (
        <div style={{ textAlign: 'center' }}>
          <div style={{
            ...mono,
            fontSize: 10,
            letterSpacing: '0.14em',
            color: 'var(--text-dim)',
          }}>
            {active ? 'AWAITING CAMERA SIGNAL' : 'SESSION INACTIVE'}
          </div>
        </div>
      )}

      {/* Corner label */}
      <div style={{
        position: 'absolute',
        top: 8,
        left: 8,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        background: 'rgba(10,10,15,0.82)',
        padding: '3px 8px',
        borderRadius: 'var(--radius-sm)',
      }}>
        {showFeed && (
          <div style={{
            width: 4,
            height: 4,
            borderRadius: '50%',
            background: 'var(--ok)',
            animation: 'status-live 1.6s ease-in-out infinite',
          }} />
        )}
        <span style={{ ...mono, fontSize: 9, letterSpacing: '0.1em', color: showFeed ? 'var(--ok)' : 'var(--text-dim)' }}>
          {showFeed ? 'YOLO v8n  /  LIVE' : 'OFFLINE'}
        </span>
      </div>
    </div>
  )
}

// ── Depth strip ───────────────────────────────────────────────────────────────

function DepthStrip({ active, camConnected }: { active: boolean; camConnected: boolean }) {
  const showFeed = active && camConnected

  return (
    <div style={{
      ...SECTION,
      height: 130,
      flexShrink: 0,
      overflow: 'hidden',
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      {showFeed ? (
        <img src="/depth" alt="MiDaS depth" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
      ) : (
        <span style={{ ...mono, fontSize: 10, letterSpacing: '0.12em', color: 'var(--text-dim)' }}>
          DEPTH OFFLINE
        </span>
      )}
      <div style={{
        position: 'absolute',
        top: 6,
        left: 8,
        background: 'rgba(10,10,15,0.82)',
        padding: '2px 7px',
        borderRadius: 'var(--radius-sm)',
      }}>
        <span style={{ ...mono, fontSize: 9, letterSpacing: '0.1em', color: 'var(--warn)' }}>
          MiDaS  /  MONOCULAR DEPTH
        </span>
      </div>
    </div>
  )
}

// ── Motor zone grid ───────────────────────────────────────────────────────────

function MotorZones({ detections, motorConnected }: { detections: string[]; motorConnected: boolean }) {
  const hasLeft   = detections.some(d => d.endsWith('left'))
  const hasCenter = detections.some(d => d.endsWith('center'))
  const hasRight  = detections.some(d => d.endsWith('right'))

  return (
    <div style={{ ...SECTION, padding: '10px 12px', flexShrink: 0 }}>
      <div style={{ ...LABEL, marginBottom: 8 }}>HAPTIC ZONES</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
        {(['LEFT', 'CENTER', 'RIGHT'] as const).map((zone) => {
          const active = zone === 'LEFT' ? hasLeft : zone === 'CENTER' ? hasCenter : hasRight
          return (
            <div
              key={zone}
              style={{
                padding: '8px 0',
                border: `1px solid ${active ? 'var(--border-accent)' : 'var(--border)'}`,
                borderRadius: 'var(--radius)',
                background: active ? 'var(--accent-dim)' : 'transparent',
                textAlign: 'center' as const,
                animation: active ? 'motor-pulse 1s ease-in-out infinite' : 'none',
                transition: 'border-color 0.25s, background 0.25s',
              }}
            >
              <div style={{
                ...mono,
                fontSize: 9,
                fontWeight: 600,
                letterSpacing: '0.14em',
                color: active ? 'var(--accent)' : motorConnected ? 'var(--text-muted)' : 'var(--text-dim)',
              }}>
                {zone}
              </div>
              <div style={{
                ...mono,
                fontSize: 8,
                letterSpacing: '0.08em',
                marginTop: 3,
                color: active ? 'var(--accent)' : 'var(--text-dim)',
              }}>
                {active ? 'FIRING' : '--'}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Detection list ────────────────────────────────────────────────────────────

const DIR_COLOR: Record<string, string> = {
  left:   'var(--warn)',
  center: 'var(--ok)',
  right:  'var(--accent)',
}

const DIR_ARROW: Record<string, string> = {
  left: 'L', center: 'C', right: 'R',
}

function DetectionList({ detections }: { detections: string[] }) {
  return (
    <div style={{ ...SECTION, padding: '10px 12px', flexShrink: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={LABEL}>DETECTIONS</div>
        <div style={{
          ...mono,
          fontSize: 9,
          color: detections.length > 0 ? 'var(--warn)' : 'var(--text-dim)',
          letterSpacing: '0.08em',
        }}>
          {detections.length > 0 ? `${detections.length} OBJECT${detections.length > 1 ? 'S' : ''}` : 'CLEAR'}
        </div>
      </div>

      {detections.length === 0 ? (
        <div style={{ ...mono, fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.08em' }}>
          No obstacles in field of view
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {detections.map((d, i) => {
            const parts = d.match(/^(.+?)\s+(left|center|right)$/i)
            const label = parts ? parts[1] : d
            const dir   = parts ? parts[2].toLowerCase() : ''
            const color = DIR_COLOR[dir] ?? 'var(--text-muted)'
            return (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '4px 8px',
                background: 'var(--surface-raised)',
                borderRadius: 'var(--radius-sm)',
                borderLeft: `2px solid ${color}`,
                animation: 'fade-in 0.15s ease-out',
              }}>
                <span style={{ ...mono, fontSize: 11, fontWeight: 500, color: 'var(--text)', flex: 1 }}>
                  {label.toUpperCase()}
                </span>
                <span style={{ ...mono, fontSize: 9, fontWeight: 600, color, letterSpacing: '0.1em' }}>
                  {DIR_ARROW[dir] ?? dir.toUpperCase()}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Chat window ───────────────────────────────────────────────────────────────

const VOICE_COLOR = {
  idle:       'var(--text-dim)',
  listening:  'var(--ok)',
  processing: 'var(--warn)',
} as const

const VOICE_LABEL = {
  idle:       'IDLE',
  listening:  'LISTENING',
  processing: 'PROCESSING',
} as const

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  const time = new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      animation: 'fade-in 0.2s ease-out',
    }}>
      <div style={{
        ...mono,
        fontSize: 9,
        color: 'var(--text-dim)',
        letterSpacing: '0.1em',
        marginBottom: 4,
      }}>
        {isUser ? 'USER' : 'ECHO'}  {time}
      </div>
      <div style={{
        maxWidth: '84%',
        padding: '9px 13px',
        borderRadius: isUser ? '4px 4px 2px 4px' : '4px 4px 4px 2px',
        background: isUser ? 'rgba(0,212,255,0.06)' : 'rgba(22,199,132,0.06)',
        border: `1px solid ${isUser ? 'rgba(0,212,255,0.18)' : 'rgba(22,199,132,0.18)'}`,
        ...sans,
        fontSize: 13,
        lineHeight: 1.55,
        color: 'var(--text)',
        fontWeight: 400,
      }}>
        {msg.text}
      </div>
    </div>
  )
}

function ChatWindow({ messages, voiceStatus }: { messages: ChatMessage[]; voiceStatus: Status['voice_status'] }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, voiceStatus])

  const dotColor = VOICE_COLOR[voiceStatus]

  return (
    <div style={{
      ...SECTION,
      display: 'flex',
      flexDirection: 'column',
      minHeight: 0,
      overflow: 'hidden',
    }}>
      {/* Chat header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 14px',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <div style={{ ...LABEL, flex: 1 }}>ECHO AI  /  VOICE TRANSCRIPT</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: dotColor,
            animation: voiceStatus !== 'idle' ? 'status-live 1s ease-in-out infinite' : 'none',
          }} />
          <span style={{
            ...mono,
            fontSize: 9,
            fontWeight: 600,
            letterSpacing: '0.1em',
            color: dotColor,
            transition: 'color 0.3s',
          }}>
            {VOICE_LABEL[voiceStatus]}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 14px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {messages.length === 0 ? (
          <div style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <div style={{
              ...mono,
              fontSize: 10,
              letterSpacing: '0.12em',
              color: 'var(--text-dim)',
              textAlign: 'center' as const,
              lineHeight: 2,
            }}>
              VOICE INTERFACE ACTIVE<br />
              <span style={{ color: 'var(--text-dim)', fontSize: 9 }}>
                SAY  "HEY ECHO"  TO BEGIN
              </span>
            </div>
          </div>
        ) : (
          messages.map((msg, i) => <ChatBubble key={i} msg={msg} />)
        )}

        {/* Processing indicator — three dots replaced with a text readout */}
        {voiceStatus === 'processing' && (
          <div style={{
            ...mono,
            fontSize: 9,
            color: 'var(--warn)',
            letterSpacing: '0.1em',
            animation: 'status-live 0.8s ease-in-out infinite',
          }}>
            ECHO  /  PROCESSING...
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Root app ──────────────────────────────────────────────────────────────────

export default function App() {
  const [status, setStatus]       = useState<Status>(EMPTY)
  const [active, setActive]       = useState(false)
  const [wsConnected, setWsConn]  = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  function startSession() {
    if (wsRef.current) return
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${window.location.host}/ws`)
    wsRef.current = ws
    ws.onopen    = () => { setWsConn(true); setActive(true) }
    ws.onclose   = () => { setWsConn(false); setActive(false); wsRef.current = null }
    ws.onmessage = (e) => { try { setStatus(JSON.parse(e.data)) } catch {} }
  }

  function stopSession() {
    wsRef.current?.close()
    wsRef.current = null
    setActive(false)
    setWsConn(false)
    setStatus(EMPTY)
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg)' }}>
      <SystemBar
        status={status}
        active={active}
        wsConnected={wsConnected}
        onStart={startSession}
        onStop={stopSession}
      />

      <main style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 12,
        padding: 12,
        minHeight: 0,
        overflow: 'hidden',
      }}>
        {/* Left column — video + depth + analysis */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0 }}>
          <CameraFeed active={active} camConnected={status.cam_connected} />
          {status.depth_enabled && (
            <DepthStrip active={active} camConnected={status.cam_connected} />
          )}
          <DetectionList detections={status.detections} />
          <MotorZones detections={status.detections} motorConnected={status.motor_connected} />
        </div>

        {/* Right column — chat */}
        <ChatWindow messages={status.chat_messages} voiceStatus={status.voice_status} />
      </main>
    </div>
  )
}
