
import { useRef } from "react";

export default function UploadPanel({
  image1,
  image2,
  hasSar,
  onImage1,
  onImage2,
  onSarToggle,
}) {
  const ref1 = useRef(null);
  const ref2 = useRef(null);

  return (
    <div className="upload-options">
      <button
        className={`upload-button ${image1 ? "selected" : ""}`}
        onClick={() => ref1.current?.click()}
      >
        + {image1 ? "Image 1 added" : "Image 1"}
      </button>

      <input
        ref={ref1}
        type="file"
        accept=".png,.jpg,.jpeg,.tif,.tiff"
        onChange={(e) => onImage1(e.target.files[0] || null)}
      />

      <button
        className={`upload-button ${image2 ? "selected" : ""}`}
        onClick={() => ref2.current?.click()}
      >
        + {image2 ? "Image 2 added" : "Image 2"}
      </button>

      <input
        ref={ref2}
        type="file"
        accept=".png,.jpg,.jpeg,.tif,.tiff"
        onChange={(e) => onImage2(e.target.files[0] || null)}
      />

      {image2 && (
        <label className="sar-option">
          <input
            type="checkbox"
            checked={hasSar}
            onChange={(e) => onSarToggle(e.target.checked)}
          />
          SAR
        </label>
      )}
    </div>
  );
}

