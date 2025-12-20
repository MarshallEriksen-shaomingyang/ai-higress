const DEFAULT_MAX_DIM = 512;
const MIN_MAX_DIM = 128;
const DEFAULT_QUALITY = 0.82;
const MIN_QUALITY = 0.5;

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Failed to load image"));
    img.src = src;
  });
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function renderJpegDataUrl(
  img: HTMLImageElement,
  options: { maxDim: number; quality: number }
): string {
  const { maxDim, quality } = options;
  const width = img.naturalWidth || img.width || 0;
  const height = img.naturalHeight || img.height || 0;
  if (!width || !height) return "";

  const maxSide = Math.max(width, height);
  const scale = maxSide > maxDim ? maxDim / maxSide : 1;
  const targetWidth = Math.max(1, Math.round(width * scale));
  const targetHeight = Math.max(1, Math.round(height * scale));

  const canvas = document.createElement("canvas");
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";

  // JPEG 不支持透明，先填充白底避免黑底。
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, targetWidth, targetHeight);
  ctx.drawImage(img, 0, 0, targetWidth, targetHeight);

  return canvas.toDataURL("image/jpeg", clamp(quality, 0, 1));
}

export type EncodeImageOptions = {
  /**
   * 目标 data URL 的最大字符数（为了兼容后端 content 长度限制）。
   * 超过则自动降分辨率/质量，直到满足或达到最低阈值。
   */
  maxChars: number;
};

/**
 * 将图片编码为尽可能小的 data URL（JPEG），用于“在不改后端接口”的前提下
 * 以文本形式携带图片（渲染侧会把 data:image... 自动嵌入为图片）。
 */
export async function encodeImageFileToCompactDataUrl(
  file: File,
  options: EncodeImageOptions
): Promise<string> {
  const original = await readAsDataUrl(file);
  const img = await loadImage(original);

  let maxDim = DEFAULT_MAX_DIM;
  let quality = DEFAULT_QUALITY;
  let last = "";

  for (let attempt = 0; attempt < 10; attempt += 1) {
    const encoded = renderJpegDataUrl(img, { maxDim, quality });
    last = encoded;
    if (encoded && encoded.length <= options.maxChars) return encoded;
    maxDim = Math.max(MIN_MAX_DIM, Math.floor(maxDim * 0.82));
    quality = Math.max(MIN_QUALITY, quality - 0.08);
  }

  return last;
}

