import { sampleField } from "./engine";
import type { SceneId } from "../scenes";

self.onmessage = ({ data }: MessageEvent<{ scene: SceneId; cols: number; rows: number; aspect: number; ss: number }>) => {
  const field = sampleField(data.scene, data.cols, data.rows, data.aspect, data.ss);
  self.postMessage(field, { transfer: [field.lum.buffer, field.zone.buffer] });
};
