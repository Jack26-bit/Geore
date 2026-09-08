import { useRef } from "react";

export default function UploadPanel({ image1, image2, hasSar, onImage1, onImage2, onSarToggle }) {
  const ref1 = useRef(null);
  const ref2 = useRef(null);

  return (
    <div>
      <p className="section-label">Image 1 (required)</p>
      <div
        className={`file-drop ${image1 ? "has-file" : ""}`}
        onClick={() => ref1.current?.click()}
      >
        {image1 ? image1.name : "Click to upload primary image"}
        <input
          ref={ref1}
          type="file"
          accept=".png,.jpg,.jpeg,.tif,.tiff"
          onChange={(e) => onImage1(e.target.files[0] || null)}
        />
      </div>

      <div style={{ marginTop: 14 }}>
        <p className="section-label">Image 2 (optional)</p>
        <div
          className={`file-drop ${image2 ? "has-file" : ""}`}
          onClick={() => ref2.current?.click()}
        >
          {image2 ? image2.name : "Click to upload second image"}
          <input
            ref={ref2}
            type="file"
            accept=".png,.jpg,.jpeg,.tif,.tiff"
            onChange={(e) => onImage2(e.target.files[0] || null)}
          />
        </div>
      </div>

      {image2 && (
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={hasSar}
            onChange={(e) => onSarToggle(e.target.checked)}
          />
          Image 2 is SAR data
        </label>
      )}
    </div>
  );
}
