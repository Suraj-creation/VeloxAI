import { CameraCard } from '@/modules/live-cameras/components/CameraCard'
import { LiveCamera } from '@/modules/live-cameras/types/camera'

type CameraHealthGridProps = {
  cameras: LiveCamera[]
}

export function CameraHealthGrid({ cameras }: CameraHealthGridProps) {
  return (
    <section className="camera-grid" id="camera-health-grid">
      {cameras.map((camera) => (
        <CameraCard key={camera.camera_id} camera={camera} />
      ))}
    </section>
  )
}
