import { useRef, useEffect, useCallback } from "react";

/**
 * ImageViewer — renders uploaded image(s) with a canvas overlay for bbox.
 *
 * The bbox overlay draws progressively over ~400ms (the one bold visual moment).
 * Normalized bbox [x_min, y_min, x_max, y_max] is converted to pixel coords
 * based on rendered image dimensions.
 *
 * The canvas is absolutely positioned inside the same position:relative wrapper
 * as the image so the overlay aligns perfectly.
 */
export default function ImageViewer({ image1Url, image2Url, image2Label, bbox }) {
  const imgRef = useRef(null);
  const canvasRef = useRef(null);
  const animRef = useRef(null);

  const drawBbox = useCallback(() => {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas || !bbox || bbox.length !== 4) return;

    // Match canvas size to rendered image size
    const rect = img.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const [xMin, yMin, xMax, yMax] = bbox;
    const x = xMin * canvas.width;
    const y = yMin * canvas.height;
    const w = (xMax - xMin) * canvas.width;
    const h = (yMax - yMin) * canvas.height;

    // Perimeter for progressive draw
    const perimeter = 2 * (w + h);
    const durationMs = 400;
    let startTime = null;

    function animate(timestamp) {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      const drawLen = progress * perimeter;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Semi-transparent fill fades in
      ctx.fillStyle = `rgba(79, 184, 176, ${0.08 * progress})`;
      ctx.fillRect(x, y, w, h);

      // Draw the rectangle path progressively
      ctx.beginPath();
      ctx.strokeStyle = "rgba(79, 184, 176, 0.9)";
      ctx.lineWidth = 2;

      let remaining = drawLen;

      // Top edge
      const topLen = Math.min(remaining, w);
      ctx.moveTo(x, y);
      ctx.lineTo(x + topLen, y);
      remaining -= topLen;

      // Right edge
      if (remaining > 0) {
        const rightLen = Math.min(remaining, h);
        ctx.lineTo(x + w, y + rightLen);
        remaining -= rightLen;
      }

      // Bottom edge (right to left)
      if (remaining > 0) {
        const bottomLen = Math.min(remaining, w);
        ctx.lineTo(x + w - bottomLen, y + h);
        remaining -= bottomLen;
      }

      // Left edge (bottom to top)
      if (remaining > 0) {
        const leftLen = Math.min(remaining, h);
        ctx.lineTo(x, y + h - leftLen);
      }

      ctx.stroke();

      if (progress < 1) {
        animRef.current = requestAnimationFrame(animate);
      }
    }

    if (animRef.current) cancelAnimationFrame(animRef.current);
    animRef.current = requestAnimationFrame(animate);
  }, [bbox]);

  useEffect(() => {
    drawBbox();
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [drawBbox]);

  // Redraw on window resize
  useEffect(() => {
    const handleResize = () => drawBbox();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [drawBbox]);

  if (!image1Url) {
    return (
      <div className="empty-viewer">
        <div className="empty-viewer-icon">&#x1F6F0;&#xFE0F;</div>
        <div>Upload a satellite image to begin</div>
      </div>
    );
  }

  const dual = !!image2Url;

  return (
    <div className={`image-viewer-container ${dual ? "dual" : ""}`}>
      <div className="image-frame">
        <img
          ref={imgRef}
          src={image1Url}
          alt="Primary satellite image"
          onLoad={drawBbox}
        />
        {bbox && (
          <canvas
            ref={canvasRef}
            className="bbox-canvas"
          />
        )}
        <div className="image-label">
          {dual ? "Image 1" : "Primary image"}
        </div>
      </div>

      {dual && (
        <div className="image-frame">
          <img src={image2Url} alt="Secondary image" />
          <div className="image-label">{image2Label || "Image 2"}</div>
        </div>
      )}
    </div>
  );
}
