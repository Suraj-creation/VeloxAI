import { useEffect, useMemo, useState } from 'react'
import { AppShell } from '@/app/layout/AppShell'
import { Badge } from '@/shared/components/Badge'
import { useLiveCamerasQuery } from '@/modules/live-cameras/hooks/useLiveCamerasQuery'
import { useDashboardSummaryQuery } from '@/modules/analytics/hooks/useDashboardSummaryQuery'
import { apiRequest, unknownSchema } from '@/shared/api/client'
import { endpoints } from '@/shared/api/endpoints'
import { env } from '@/shared/config/env'

type SourceMode = 'device' | 'rtsp'

type CameraLabConfig = {
  cameraId: string
  locationName: string
  gpsLat: string
  gpsLng: string
  sourceMode: SourceMode
  sourceValue: string
  selectedDeviceId: string
  previewWidth: number
  previewHeight: number
  targetFps: number
  detectionConfidence: number
  speedThresholdKmph: number
  minOcrConfidence: number
  cooldownSec: number
  generalModel: string
  enforcementModel: string
  enablePlatePipeline: boolean
}

type ConnectionReport = {
  backendQueryApi: boolean
  backendSummaryApi: boolean
  edgeRuntimeApi: boolean
  edgeRuntimeRunning: boolean
  edgePreviewFrame: boolean
  selectedCameraFound: boolean
  modelProfilesReady: boolean
  checkedAt: string
}

type EdgeRuntimeState = {
  reachable: boolean
  running: boolean
  hasPreviewFrame: boolean
  previewUpdatedAt: string | null
  status: string | null
  frameFailures: number
  reconnects: number
  sourceCamera: string | null
  signalMeanLuma: number | null
  signalStdLuma: number | null
}

const STORAGE_KEY = 'footwatch.camera-lab.config.v1'

const DEFAULT_CONFIG: CameraLabConfig = {
  cameraId: 'FP_CAM_001',
  locationName: 'Sample Junction',
  gpsLat: '12.9716',
  gpsLng: '77.5946',
  sourceMode: 'device',
  sourceValue: '0',
  selectedDeviceId: '',
  previewWidth: 1280,
  previewHeight: 720,
  targetFps: 15,
  detectionConfidence: 0.35,
  speedThresholdKmph: 5,
  minOcrConfidence: 0.65,
  cooldownSec: 60,
  generalModel: 'YOLOv8n General Objects',
  enforcementModel: 'YOLOv8n Two-Wheeler + LP + PaddleOCR',
  enablePlatePipeline: true,
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function hydrateConfig(raw: unknown): CameraLabConfig {
  if (!raw || typeof raw !== 'object') {
    return DEFAULT_CONFIG
  }

  const value = raw as Partial<CameraLabConfig>

  return {
    ...DEFAULT_CONFIG,
    ...value,
    sourceMode: value.sourceMode === 'rtsp' ? 'rtsp' : 'device',
    previewWidth: clamp(Number(value.previewWidth ?? DEFAULT_CONFIG.previewWidth), 320, 3840),
    previewHeight: clamp(Number(value.previewHeight ?? DEFAULT_CONFIG.previewHeight), 240, 2160),
    targetFps: clamp(Number(value.targetFps ?? DEFAULT_CONFIG.targetFps), 1, 60),
    detectionConfidence: clamp(Number(value.detectionConfidence ?? DEFAULT_CONFIG.detectionConfidence), 0.1, 0.95),
    speedThresholdKmph: clamp(Number(value.speedThresholdKmph ?? DEFAULT_CONFIG.speedThresholdKmph), 1, 50),
    minOcrConfidence: clamp(Number(value.minOcrConfidence ?? DEFAULT_CONFIG.minOcrConfidence), 0.3, 0.99),
    cooldownSec: clamp(Number(value.cooldownSec ?? DEFAULT_CONFIG.cooldownSec), 5, 600),
    cameraId: String(value.cameraId ?? DEFAULT_CONFIG.cameraId),
    locationName: String(value.locationName ?? DEFAULT_CONFIG.locationName),
    gpsLat: String(value.gpsLat ?? DEFAULT_CONFIG.gpsLat),
    gpsLng: String(value.gpsLng ?? DEFAULT_CONFIG.gpsLng),
    sourceValue: String(value.sourceValue ?? DEFAULT_CONFIG.sourceValue),
    selectedDeviceId: String(value.selectedDeviceId ?? DEFAULT_CONFIG.selectedDeviceId),
    generalModel: String(value.generalModel ?? DEFAULT_CONFIG.generalModel),
    enforcementModel: String(value.enforcementModel ?? DEFAULT_CONFIG.enforcementModel),
    enablePlatePipeline: Boolean(value.enablePlatePipeline ?? DEFAULT_CONFIG.enablePlatePipeline),
  }
}

function loadStoredConfig(): CameraLabConfig {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return DEFAULT_CONFIG
    }

    return hydrateConfig(JSON.parse(raw))
  } catch {
    return DEFAULT_CONFIG
  }
}

function stopStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop())
}

function parseDeviceIndex(raw: string): number | null {
  const parsed = Number(raw)
  if (!Number.isInteger(parsed) || parsed < 0) {
    return null
  }

  return parsed
}

export function CameraLabPage() {
  const [config, setConfig] = useState<CameraLabConfig>(() => loadStoredConfig())
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [saveMessage, setSaveMessage] = useState<string>('')
  const [runningChecks, setRunningChecks] = useState(false)
  const [connectionReport, setConnectionReport] = useState<ConnectionReport | null>(null)
  const [edgeRuntime, setEdgeRuntime] = useState<EdgeRuntimeState>({
    reachable: false,
    running: false,
    hasPreviewFrame: false,
    previewUpdatedAt: null,
    status: null,
    frameFailures: 0,
    reconnects: 0,
    sourceCamera: null,
    signalMeanLuma: null,
    signalStdLuma: null,
  })
  const [edgeFrameTick, setEdgeFrameTick] = useState(0)

  const liveQuery = useLiveCamerasQuery()
  const summaryQuery = useDashboardSummaryQuery()

  const selectedCameraFromBackend = useMemo(() => {
    return (liveQuery.data?.items ?? []).find((item) => item.camera_id === config.cameraId)
  }, [liveQuery.data, config.cameraId])

  const selectedSourceIndex = useMemo(() => {
    if (config.sourceMode !== 'device') {
      return null
    }

    return parseDeviceIndex(config.sourceValue)
  }, [config.sourceMode, config.sourceValue])

  const selectedSourceDevice = useMemo(() => {
    if (selectedSourceIndex == null) {
      return undefined
    }

    return devices[selectedSourceIndex]
  }, [devices, selectedSourceIndex])

  const selectedRuntimeDeviceId = useMemo(() => {
    if (config.sourceMode !== 'device') {
      return ''
    }

    const hasStoredDevice = devices.some((device) => device.deviceId === config.selectedDeviceId)
    if (config.selectedDeviceId && hasStoredDevice) {
      return config.selectedDeviceId
    }

    return selectedSourceDevice?.deviceId ?? ''
  }, [config.sourceMode, config.selectedDeviceId, devices, selectedSourceDevice])

  const generatedCliCommand = useMemo(() => {
    const sourceToken =
      config.sourceMode === 'device' ? config.sourceValue || '0' : config.sourceValue || '<rtsp-url>'

    return `.\\.venv\\Scripts\\python.exe .\\main.py --source ${sourceToken} --frames 300`
  }, [config.sourceMode, config.sourceValue])

  const edgeFrameUrl = useMemo(() => {
    return `${env.VITE_API_BASE_URL}${endpoints.edgeRuntimeFrame}?t=${edgeFrameTick}`
  }, [edgeFrameTick])

  const loadConfigFromBackend = async () => {
    try {
      const payload = await apiRequest(endpoints.edgeConfig, { schema: unknownSchema })
      const record = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null
      const resolved = record?.resolved
      if (!resolved || typeof resolved !== 'object') {
        setSaveMessage('Backend config response is missing resolved values.')
        return
      }

      setConfig((prev) => hydrateConfig({ ...prev, ...(resolved as Record<string, unknown>) }))
      setSaveMessage('Configuration loaded from edge runtime backend.')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load backend config.'
      setSaveMessage(`Failed to load backend config: ${message}`)
    }
  }

  const fetchEdgeRuntimeStatus = async (): Promise<EdgeRuntimeState> => {
    try {
      const payload = await apiRequest(endpoints.edgeRuntimeStatus, { schema: unknownSchema })
      const record = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null
      const runtime = record?.runtime

      if (!runtime || typeof runtime !== 'object') {
        const fallback = {
          reachable: false,
          running: false,
          hasPreviewFrame: false,
          previewUpdatedAt: null,
          status: null,
          frameFailures: 0,
          reconnects: 0,
          sourceCamera: null,
          signalMeanLuma: null,
          signalStdLuma: null,
        }
        setEdgeRuntime(fallback)
        return fallback
      }

      const runtimeRecord = runtime as Record<string, unknown>
      const metricsRecord =
        record?.metrics && typeof record.metrics === 'object' ? (record.metrics as Record<string, unknown>) : null
      const statsRecord =
        metricsRecord?.stats && typeof metricsRecord.stats === 'object'
          ? (metricsRecord.stats as Record<string, unknown>)
          : null

      const nextState: EdgeRuntimeState = {
        reachable: true,
        running: Boolean(runtimeRecord.running),
        hasPreviewFrame: Boolean(runtimeRecord.has_preview_frame),
        previewUpdatedAt:
          typeof runtimeRecord.preview_updated_at === 'string' ? runtimeRecord.preview_updated_at : null,
        status: typeof statsRecord?.status === 'string' ? statsRecord.status : null,
        frameFailures: Number(statsRecord?.frame_failures ?? 0),
        reconnects: Number(statsRecord?.reconnects ?? 0),
        sourceCamera: typeof statsRecord?.source_camera === 'string' ? statsRecord.source_camera : null,
        signalMeanLuma: typeof statsRecord?.signal_mean_luma === 'number' ? Number(statsRecord.signal_mean_luma) : null,
        signalStdLuma: typeof statsRecord?.signal_std_luma === 'number' ? Number(statsRecord.signal_std_luma) : null,
      }

      setEdgeRuntime((previous) => {
        if (
          nextState.hasPreviewFrame &&
          nextState.previewUpdatedAt &&
          nextState.previewUpdatedAt !== previous.previewUpdatedAt
        ) {
          setEdgeFrameTick(Date.now())
        }
        return nextState
      })

      return nextState
    } catch {
      const fallback = {
        reachable: false,
        running: false,
        hasPreviewFrame: false,
        previewUpdatedAt: null,
        status: null,
        frameFailures: 0,
        reconnects: 0,
        sourceCamera: null,
        signalMeanLuma: null,
        signalStdLuma: null,
      }
      setEdgeRuntime(fallback)
      return fallback
    }
  }

  const refreshDevices = async (requestPermission: boolean): Promise<MediaDeviceInfo[]> => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      setDevices([])
      return []
    }

    if (requestPermission && navigator.mediaDevices?.getUserMedia) {
      try {
        const warmupStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        stopStream(warmupStream)
      } catch {
        // Ignore warmup permission errors; fallback enumeration still runs.
      }
    }

    try {
      const all = await navigator.mediaDevices.enumerateDevices()
      const cams = all.filter((item) => item.kind === 'videoinput')
      setDevices(cams)
      return cams
    } catch {
      setDevices([])
      return []
    }
  }

  useEffect(() => {
    void refreshDevices(false)
    void loadConfigFromBackend()
    void fetchEdgeRuntimeStatus()

    const handleDeviceChange = () => {
      void refreshDevices(false)
    }

    navigator.mediaDevices?.addEventListener?.('devicechange', handleDeviceChange)

    return () => {
      navigator.mediaDevices?.removeEventListener?.('devicechange', handleDeviceChange)
    }
  }, [])

  useEffect(() => {
    const id = window.setInterval(() => {
      void fetchEdgeRuntimeStatus()
    }, 1200)

    return () => {
      window.clearInterval(id)
    }
  }, [])

  const updateConfig = <K extends keyof CameraLabConfig>(key: K, value: CameraLabConfig[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
    setSaveMessage('')
  }

  const selectEdgeRuntimeDevice = async (deviceId: string) => {
    if (config.sourceMode !== 'device') {
      return
    }

    const index = devices.findIndex((device) => device.deviceId === deviceId)
    if (index < 0) {
      return
    }

    const nextConfig: CameraLabConfig = {
      ...config,
      sourceValue: String(index),
      selectedDeviceId: deviceId,
    }

    setConfig(nextConfig)
    setSaveMessage('Updating edge runtime camera...')

    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextConfig))
      await apiRequest(endpoints.edgeConfig, {
        method: 'PUT',
        body: nextConfig,
        schema: unknownSchema,
      })
      setSaveMessage('Edge runtime camera updated and synced to backend.')
      void fetchEdgeRuntimeStatus()
    } catch {
      setSaveMessage('Camera selection saved locally, but failed to sync with edge runtime backend.')
    }
  }

  const saveConfig = async () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
      await apiRequest(endpoints.edgeConfig, {
        method: 'PUT',
        body: config,
        schema: unknownSchema,
      })
      setSaveMessage('Configuration saved locally and synced to edge runtime backend.')
    } catch {
      setSaveMessage('Saved locally, but failed to sync with edge runtime backend.')
    }
  }

  const resetConfig = () => {
    setConfig(DEFAULT_CONFIG)
    setSaveMessage('Configuration reset to defaults. Save to persist.')
  }

  const exportConfig = () => {
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'camera-lab-config.json'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  const importConfig = async (file: File | undefined) => {
    if (!file) {
      return
    }

    try {
      const content = await file.text()
      const parsed = JSON.parse(content)
      setConfig(hydrateConfig(parsed))
      setSaveMessage('Configuration imported. Save to persist it.')
    } catch {
      setSaveMessage('Invalid JSON configuration file.')
    }
  }

  const runConnectionChecks = async () => {
    setRunningChecks(true)

    const [liveResult, summaryResult, edgeResult] = await Promise.all([
      liveQuery.refetch(),
      summaryQuery.refetch(),
      fetchEdgeRuntimeStatus(),
    ])

    setConnectionReport({
      backendQueryApi: !liveResult.error,
      backendSummaryApi: !summaryResult.error,
      edgeRuntimeApi: edgeResult.reachable,
      edgeRuntimeRunning: edgeResult.running,
      edgePreviewFrame: edgeResult.hasPreviewFrame,
      selectedCameraFound: Boolean((liveResult.data?.items ?? []).some((item) => item.camera_id === config.cameraId)),
      modelProfilesReady: Boolean(config.generalModel && config.enforcementModel),
      checkedAt: new Date().toLocaleString(),
    })

    setRunningChecks(false)
  }

  return (
    <AppShell>
      <section className="camera-lab-grid">
        <section className="section-card" id="camera-lab-config">
          <div className="section-header">
            <span className="section-icon">🎛️</span>
            <h2 style={{ marginBottom: 0 }}>Camera & Runtime Configuration</h2>
            <Badge tone="info">Frontend Controlled</Badge>
          </div>

          <div className="camera-config-grid" style={{ marginBottom: '1rem' }}>
            <label className="camera-lab-field">
              <span className="text-xs muted">Camera ID</span>
              <input value={config.cameraId} onChange={(event) => updateConfig('cameraId', event.target.value)} />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">Location Name</span>
              <input value={config.locationName} onChange={(event) => updateConfig('locationName', event.target.value)} />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">GPS Latitude</span>
              <input value={config.gpsLat} onChange={(event) => updateConfig('gpsLat', event.target.value)} />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">GPS Longitude</span>
              <input value={config.gpsLng} onChange={(event) => updateConfig('gpsLng', event.target.value)} />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">Source Mode</span>
              <select
                value={config.sourceMode}
                onChange={(event) => updateConfig('sourceMode', event.target.value === 'rtsp' ? 'rtsp' : 'device')}
              >
                <option value="device">USB / Built-in Camera</option>
                <option value="rtsp">RTSP Stream</option>
              </select>
            </label>
            {config.sourceMode === 'rtsp' ? (
              <label className="camera-lab-field">
                <span className="text-xs muted">Source Value (URL)</span>
                <input
                  value={config.sourceValue}
                  onChange={(event) => updateConfig('sourceValue', event.target.value)}
                  placeholder="rtsp://camera-stream"
                />
              </label>
            ) : (
              <label className="camera-lab-field">
                <span className="text-xs muted">Edge Runtime Camera (device mode)</span>
                <select
                  value={selectedRuntimeDeviceId}
                  onChange={(event) => void selectEdgeRuntimeDevice(event.target.value)}
                  disabled={devices.length === 0}
                >
                  <option value="" disabled>
                    {devices.length === 0 ? 'No camera devices detected' : 'Select camera'}
                  </option>
                  {devices.map((device, index) => (
                    <option key={device.deviceId} value={device.deviceId}>
                      [{index}] {device.label || `Camera ${index + 1}`}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="camera-lab-field">
              <span className="text-xs muted">Preview Width</span>
              <input
                type="number"
                value={config.previewWidth}
                min={320}
                max={3840}
                onChange={(event) => updateConfig('previewWidth', Number(event.target.value || 320))}
              />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">Preview Height</span>
              <input
                type="number"
                value={config.previewHeight}
                min={240}
                max={2160}
                onChange={(event) => updateConfig('previewHeight', Number(event.target.value || 240))}
              />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">Target FPS</span>
              <input
                type="number"
                value={config.targetFps}
                min={1}
                max={60}
                onChange={(event) => updateConfig('targetFps', Number(event.target.value || 1))}
              />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">Detection Confidence</span>
              <input
                type="number"
                step="0.01"
                value={config.detectionConfidence}
                min={0.1}
                max={0.95}
                onChange={(event) => updateConfig('detectionConfidence', Number(event.target.value || 0.1))}
              />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">Speed Threshold (km/h)</span>
              <input
                type="number"
                step="0.1"
                value={config.speedThresholdKmph}
                min={1}
                max={50}
                onChange={(event) => updateConfig('speedThresholdKmph', Number(event.target.value || 1))}
              />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">Minimum OCR Confidence</span>
              <input
                type="number"
                step="0.01"
                value={config.minOcrConfidence}
                min={0.3}
                max={0.99}
                onChange={(event) => updateConfig('minOcrConfidence', Number(event.target.value || 0.3))}
              />
            </label>
            <label className="camera-lab-field">
              <span className="text-xs muted">Per-Track Cooldown (sec)</span>
              <input
                type="number"
                value={config.cooldownSec}
                min={5}
                max={600}
                onChange={(event) => updateConfig('cooldownSec', Number(event.target.value || 5))}
              />
            </label>
          </div>

          <div className="camera-config-actions">
            <button className="btn-primary" type="button" onClick={() => void saveConfig()}>Save Configuration</button>
            <button className="btn-ghost" type="button" onClick={() => void loadConfigFromBackend()}>Pull Edge Config</button>
            <button className="btn-ghost" type="button" onClick={resetConfig}>Reset Defaults</button>
            <button className="btn-ghost" type="button" onClick={exportConfig}>Export JSON</button>
            <label className="btn-ghost camera-import-btn">
              Import JSON
              <input
                type="file"
                accept="application/json,.json"
                onChange={(event) => void importConfig(event.target.files?.[0])}
              />
            </label>
          </div>

          <p className="text-xs muted" style={{ marginTop: '0.75rem' }}>
            Camera selection above is the single source for edge runtime detection. It syncs source index and selected device to backend.
          </p>

          {saveMessage ? <p className="text-sm muted" style={{ marginTop: '0.8rem' }}>{saveMessage}</p> : null}
        </section>

        <section className="section-card" id="camera-lab-preview">
          <div className="section-header">
            <span className="section-icon">🎥</span>
            <h2 style={{ marginBottom: 0 }}>Edge Model Preview</h2>
            <Badge tone={edgeRuntime.running ? 'success' : 'warning'}>
              {edgeRuntime.running ? 'Edge Runtime Live' : 'Edge Runtime Offline'}
            </Badge>
          </div>

          <p className="camera-preview-caption">Edge Model Annotated Feed (Rectangles / Detection)</p>
          <div className="camera-preview-shell">
            {edgeRuntime.hasPreviewFrame ? (
              <img src={edgeFrameUrl} alt="Edge annotated preview" className="camera-preview-image" />
            ) : (
              <p className="text-sm muted" style={{ textAlign: 'center', padding: '1rem' }}>
                No annotated frame yet. Run the edge runtime script and verify camera source index plus lens/privacy shutter.
              </p>
            )}
          </div>

          {edgeRuntime.status === 'waiting_frame' ? (
            <p className="text-sm muted" style={{ marginTop: '0.75rem' }}>
              Edge runtime is running but currently cannot grab frames from source {edgeRuntime.sourceCamera ?? config.sourceValue}. Frame failures: {edgeRuntime.frameFailures}. Reconnect attempts: {edgeRuntime.reconnects}.
            </p>
          ) : null}

          {edgeRuntime.status === 'signal_flat' ? (
            <p className="text-sm muted" style={{ marginTop: '0.75rem' }}>
              Edge runtime is receiving a flat camera signal (mean luma {edgeRuntime.signalMeanLuma ?? 'N/A'}, std {edgeRuntime.signalStdLuma ?? 'N/A'}). Check lens/privacy shutter, lighting, and select the correct physical camera.
            </p>
          ) : null}

          <div className="camera-config-actions" style={{ marginTop: '1rem' }}>
            <button className="btn-primary" type="button" onClick={() => void refreshDevices(true)}>Refresh Camera List</button>
            <button className="btn-ghost" type="button" onClick={() => void fetchEdgeRuntimeStatus()}>Refresh Edge Preview</button>
          </div>

          <div className="camera-lab-metrics-grid" style={{ marginTop: '1rem' }}>
            <div className="camera-metric-item">
              <span className="text-xs muted">Detected Devices</span>
              <strong>{devices.length}</strong>
            </div>
            <div className="camera-metric-item">
              <span className="text-xs muted">Edge Source Camera</span>
              <strong>{selectedSourceDevice?.label || edgeRuntime.sourceCamera || `Index ${config.sourceValue}`}</strong>
            </div>
            <div className="camera-metric-item">
              <span className="text-xs muted">Source Value (Index / URL)</span>
              <strong>{config.sourceValue || 'N/A'}</strong>
            </div>
            <div className="camera-metric-item">
              <span className="text-xs muted">Edge Runtime Status</span>
              <strong>{edgeRuntime.status || 'unknown'}</strong>
            </div>
            <div className="camera-metric-item">
              <span className="text-xs muted">Frame Failures</span>
              <strong>{edgeRuntime.frameFailures}</strong>
            </div>
            <div className="camera-metric-item">
              <span className="text-xs muted">Reconnects</span>
              <strong>{edgeRuntime.reconnects}</strong>
            </div>
          </div>
        </section>
      </section>

      <section className="camera-lab-grid">
        <section className="section-card" id="camera-lab-model-profiles">
          <div className="section-header">
            <span className="section-icon">🤖</span>
            <h2 style={{ marginBottom: 0 }}>Dual Model Profiles</h2>
          </div>

          <div className="camera-model-grid">
            <article className="model-card">
              <div className="model-card-header">
                <h3>General Detection Profile</h3>
                <span className="model-tag">Model A</span>
              </div>
              <label className="camera-lab-field">
                <span className="text-xs muted">Model Label</span>
                <input
                  value={config.generalModel}
                  onChange={(event) => updateConfig('generalModel', event.target.value)}
                />
              </label>
              <p className="text-sm muted" style={{ marginTop: '0.6rem' }}>
                Used for broad object detection and camera framing checks before enforcement mode.
              </p>
            </article>

            <article className="model-card">
              <div className="model-card-header">
                <h3>Footpath Enforcement Profile</h3>
                <span className="model-tag">Model B</span>
              </div>
              <label className="camera-lab-field">
                <span className="text-xs muted">Model Label</span>
                <input
                  value={config.enforcementModel}
                  onChange={(event) => updateConfig('enforcementModel', event.target.value)}
                />
              </label>
              <label className="camera-lab-toggle" style={{ marginTop: '0.8rem' }}>
                <input
                  type="checkbox"
                  checked={config.enablePlatePipeline}
                  onChange={(event) => updateConfig('enablePlatePipeline', event.target.checked)}
                />
                <span>Enable plate localizer + OCR in enforcement profile</span>
              </label>
            </article>
          </div>

          <div className="divider" />

          <p className="text-xs muted">Generated runtime command preview</p>
          <pre className="camera-command-preview">{generatedCliCommand}</pre>
        </section>

        <section className="section-card" id="camera-lab-connections">
          <div className="section-header">
            <span className="section-icon">🔗</span>
            <h2 style={{ marginBottom: 0 }}>Connection & Health Checks</h2>
          </div>

          <div className="camera-config-actions" style={{ marginBottom: '1rem' }}>
            <button className="btn-primary" type="button" onClick={() => void runConnectionChecks()} disabled={runningChecks}>
              {runningChecks ? 'Running Checks...' : 'Run Full Check'}
            </button>
          </div>

          {connectionReport ? (
            <ul className="camera-check-list">
              <li>
                <span>Backend Live Camera Endpoint</span>
                <Badge tone={connectionReport.backendQueryApi ? 'success' : 'danger'}>
                  {connectionReport.backendQueryApi ? 'Reachable' : 'Error'}
                </Badge>
              </li>
              <li>
                <span>Backend Summary Endpoint</span>
                <Badge tone={connectionReport.backendSummaryApi ? 'success' : 'danger'}>
                  {connectionReport.backendSummaryApi ? 'Reachable' : 'Error'}
                </Badge>
              </li>
              <li>
                <span>Edge Runtime API</span>
                <Badge tone={connectionReport.edgeRuntimeApi ? 'success' : 'danger'}>
                  {connectionReport.edgeRuntimeApi ? 'Reachable' : 'Error'}
                </Badge>
              </li>
              <li>
                <span>Edge Runtime Process</span>
                <Badge tone={connectionReport.edgeRuntimeRunning ? 'success' : 'warning'}>
                  {connectionReport.edgeRuntimeRunning ? 'Running' : 'Not Running'}
                </Badge>
              </li>
              <li>
                <span>Annotated Preview Frame</span>
                <Badge tone={connectionReport.edgePreviewFrame ? 'success' : 'warning'}>
                  {connectionReport.edgePreviewFrame ? 'Available' : 'Missing'}
                </Badge>
              </li>
              <li>
                <span>Selected Camera ID in Backend Feed</span>
                <Badge tone={connectionReport.selectedCameraFound ? 'success' : 'warning'}>
                  {connectionReport.selectedCameraFound ? 'Present' : 'Not Yet Seen'}
                </Badge>
              </li>
              <li>
                <span>Dual Model Profile Completeness</span>
                <Badge tone={connectionReport.modelProfilesReady ? 'success' : 'warning'}>
                  {connectionReport.modelProfilesReady ? 'Configured' : 'Missing Labels'}
                </Badge>
              </li>
            </ul>
          ) : (
            <p className="text-sm muted">Run checks to validate frontend camera access and backend connectivity.</p>
          )}

          {connectionReport ? <p className="text-xs muted" style={{ marginTop: '0.75rem' }}>Checked at {connectionReport.checkedAt}</p> : null}

          <div className="divider" />

          <div className="camera-lab-metrics-grid">
            <div className="camera-metric-item">
              <span className="text-xs muted">Backend Cameras Online</span>
              <strong>{liveQuery.data?.items.length ?? 0}</strong>
            </div>
            <div className="camera-metric-item">
              <span className="text-xs muted">Total Violations (Summary)</span>
              <strong>{summaryQuery.data?.total_violations ?? 0}</strong>
            </div>
            <div className="camera-metric-item">
              <span className="text-xs muted">Selected Camera Status</span>
              <strong>{selectedCameraFromBackend?.status ?? 'unknown'}</strong>
            </div>
            <div className="camera-metric-item">
              <span className="text-xs muted">Edge Preview Updated</span>
              <strong>{edgeRuntime.previewUpdatedAt ?? 'N/A'}</strong>
            </div>
          </div>
        </section>
      </section>
    </AppShell>
  )
}
