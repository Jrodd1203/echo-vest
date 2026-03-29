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

// ── Indicator ─────────────────────────────────────────────────────────────────

interface IndicatorProps {
  live: boolean
  name: string
  liveLabel?: string
  offLabel?: string
  color?: string
}

function Indicator({ live, name, liveLabel = 'ONLINE', offLabel = 'OFFLINE', color = 'var(--ok)' }: IndicatorProps) {
  return (
    <div className="indicator">
      <span className="indicator-name">{name}</span>
      <div className="indicator-state">
        <div
          className={`indicator-dot${live ? ' live' : ''}`}
          style={{ background: live ? color : undefined }}
        />
        <span className="indicator-value" style={{ color: live ? color : undefined }}>
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
  return (
    <header className="header">
      <div className="wordmark">
        <div className={`wordmark-dot${active ? ' active' : ''}`} />
        <span className="wordmark-text">ECHO VEST</span>
      </div>

      <div className="header-divider" />

      <Indicator live={status.cam_connected}                  name="CAM"    liveLabel="LIVE"    offLabel="NO SIGNAL" />
      <Indicator live={status.motor_connected}                name="HAPTICS"                                         />
      <Indicator live={active}                                name="YOLO"   liveLabel="RUNNING" color="var(--accent)" />
      <Indicator live={active && status.depth_enabled}        name="DEPTH"  liveLabel="ACTIVE"  color="var(--accent)" />

      <div className="header-divider" />

      <Indicator live={wsConnected} name="DASHBOARD" liveLabel="CONNECTED" color="var(--accent)" />

      <div style={{ marginLeft: 'auto' }}>
        <button
          className={`btn-session ${active ? 'stop' : 'start'}`}
          onClick={active ? onStop : onStart}
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
    <div className="surface camera-feed">
      {showFeed ? (
        <img src="/raw" alt="Camera feed" />
      ) : (
        <span className="camera-offline">
          {active ? 'AWAITING CAMERA SIGNAL' : 'SESSION INACTIVE'}
        </span>
      )}
      <div className="feed-badge">
        {showFeed && <div className="feed-badge-dot" />}
        <span className="feed-badge-text" style={{ color: showFeed ? 'var(--ok)' : 'var(--text-dim)' }}>
          {showFeed ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>
    </div>
  )
}

// ── Depth strip ───────────────────────────────────────────────────────────────

function DepthStrip({ active, camConnected }: { active: boolean; camConnected: boolean }) {
  const showFeed = active && camConnected
  return (
    <div className="surface depth-strip">
      {showFeed
        ? <img src="/depth" alt="MiDaS depth" />
        : <span className="depth-offline">DEPTH OFFLINE</span>
      }
      <div className="depth-badge">MiDaS  /  MONOCULAR DEPTH</div>
    </div>
  )
}

// ── Detection list ────────────────────────────────────────────────────────────

const DIR_COLOR: Record<string, string> = {
  left:   'var(--warn)',
  center: 'var(--ok)',
  right:  'var(--accent)',
}

function DetectionList({ detections }: { detections: string[] }) {
  return (
    <div className="surface detections">
      <div className="detections-header">
        <span className="label">DETECTIONS</span>
        <span
          className="detections-count"
          style={{ color: detections.length > 0 ? 'var(--warn)' : 'var(--text-dim)' }}
        >
          {detections.length > 0 ? `${detections.length} OBJECT${detections.length > 1 ? 'S' : ''}` : 'CLEAR'}
        </span>
      </div>

      {detections.length === 0 ? (
        <span className="detections-empty">No obstacles in field of view</span>
      ) : (
        <div className="detections-list">
          {detections.map((d, i) => {
            const parts = d.match(/^(.+?)\s+(left|center|right)$/i)
            const label = parts ? parts[1] : d
            const dir   = parts ? parts[2].toLowerCase() : ''
            const color = DIR_COLOR[dir] ?? 'var(--text-muted)'
            return (
              <div
                key={i}
                className="detection-row"
                style={{ borderLeftColor: color }}
              >
                <span className="detection-label">{label.toUpperCase()}</span>
                <span className="detection-dir" style={{ color }}>{dir.toUpperCase()}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Motor zones ───────────────────────────────────────────────────────────────

function MotorZones({ detections, motorConnected }: { detections: string[]; motorConnected: boolean }) {
  const active = {
    LEFT:   detections.some(d => d.endsWith('left')),
    CENTER: detections.some(d => d.endsWith('center')),
    RIGHT:  detections.some(d => d.endsWith('right')),
  }

  return (
    <div className="surface motor-zones">
      <span className="label">HAPTIC ZONES</span>
      <div className="motor-grid">
        {(['LEFT', 'CENTER', 'RIGHT'] as const).map(zone => (
          <div key={zone} className={`motor-zone${active[zone] ? ' firing' : ''}`}>
            <div className="motor-zone-name">{zone}</div>
            <div className="motor-zone-status">
              {!motorConnected ? 'N/C' : active[zone] ? 'FIRING' : '--'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Chat ──────────────────────────────────────────────────────────────────────

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
    <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-echo'}`}>
      <span className="bubble-meta">{isUser ? 'USER' : 'ECHO'}  {time}</span>
      <div className="bubble-body">{msg.text}</div>
    </div>
  )
}

function ChatWindow({ messages, voiceStatus }: { messages: ChatMessage[]; voiceStatus: Status['voice_status'] }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, voiceStatus])

  const dotColor   = VOICE_COLOR[voiceStatus]
  const voiceLabel = VOICE_LABEL[voiceStatus]

  return (
    <div className="surface chat">
      <div className="chat-header">
        <span className="label chat-header-label">ECHO AI  /  VOICE TRANSCRIPT</span>
        <div
          className={`voice-dot${voiceStatus !== 'idle' ? ' active' : ''}`}
          style={{ background: dotColor }}
        />
        <span className="voice-label" style={{ color: dotColor }}>{voiceLabel}</span>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-empty-text">
              VOICE INTERFACE ACTIVE<br />
              <span className="chat-empty-sub">SAY  "HEY ECHO"  TO BEGIN</span>
            </div>
          </div>
        ) : (
          messages.map((msg, i) => <ChatBubble key={i} msg={msg} />)
        )}

        {voiceStatus === 'processing' && (
          <span className="processing-indicator">ECHO  /  PROCESSING...</span>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [status, setStatus]      = useState<Status>(EMPTY)
  const [active, setActive]      = useState(false)
  const [wsConnected, setWsConn] = useState(false)
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
    <div className="app">
      <SystemBar
        status={status}
        active={active}
        wsConnected={wsConnected}
        onStart={startSession}
        onStop={stopSession}
      />
      <main className="main">
        <div className="left-col">
          <CameraFeed active={active} camConnected={status.cam_connected} />
          {status.depth_enabled && (
            <DepthStrip active={active} camConnected={status.cam_connected} />
          )}
          <DetectionList detections={status.detections} />
          <MotorZones detections={status.detections} motorConnected={status.motor_connected} />
        </div>
        <ChatWindow messages={status.chat_messages} voiceStatus={status.voice_status} />
      </main>
    </div>
  )
}
