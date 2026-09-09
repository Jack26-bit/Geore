import { useRef, useState } from "react";

const validImageTypes = [
  "image/png",
  "image/jpeg",
  "image/jpg",
  "image/tiff",
  "image/tif",
];

function isValidImageFile(file) {
  if (!file) return false;

  const name = file.name?.toLowerCase() || "";
  const type = file.type?.toLowerCase() || "";

  return (
    validImageTypes.includes(type) ||
    /\.(png|jpe?g|tiff?)$/i.test(name)
  );
}

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
  const [drag1, setDrag1] = useState(false);
  const [drag2, setDrag2] = useState(false);

  const handleFileSelection = (file, onSet) => {
    if (!isValidImageFile(file)) return;
    onSet(file);
  };

  const renderUploadCard = ({
    image,
    label,
    helperText,
    placeholder,
    refInput,
    onSet,
    dragState,
    setDragState,
    inputLabel,
  }) => {
    const isBusy = dragState;

    return (
      <div
        className={`upload-box ${image ? "has-file" : ""} ${isBusy ? "is-dragging" : ""}`}
        onClick={() => refInput.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragState(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragState(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragState(false);
          handleFileSelection(e.dataTransfer.files?.[0], onSet);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            refInput.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
        aria-label={inputLabel}
      >
        <input
          ref={refInput}
          type="file"
          accept=".png,.jpg,.jpeg,.tif,.tiff,image/png,image/jpeg,image/tiff"
          onChange={(e) => handleFileSelection(e.target.files?.[0], onSet)}
          className="upload-input"
          aria-label={inputLabel}
        />

        <div className="upload-content">
          <div className="upload-arrow">↑</div>

          <div className="upload-title">
            {image ? "Selected file" : placeholder}
          </div>

          <div className="upload-format">{helperText}</div>

          {image ? (
            <div className="file-name-row">
              <span className="upload-file-icon">📁</span>
              <span className="file-name">{image.name}</span>
            </div>
          ) : (
            <div className="upload-hint">Click or drag &amp; drop</div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div>
      <p className="section-label">PRIMARY IMAGE</p>

      {renderUploadCard({
        image: image1,
        label: "PRIMARY IMAGE",
        helperText: "PNG, JPG or TIFF",
        placeholder: "Upload primary image",
        refInput: ref1,
        onSet: onImage1,
        dragState: drag1,
        setDragState: setDrag1,
        inputLabel: "Upload primary image",
      })}

      <div style={{ marginTop: 18 }}>
        <p className="section-label">COMPARISON IMAGE (OPTIONAL)</p>

        {renderUploadCard({
          image: image2,
          label: "COMPARISON IMAGE (OPTIONAL)",
          helperText: "Useful for comparing two images",
          placeholder: "Upload comparison image",
          refInput: ref2,
          onSet: onImage2,
          dragState: drag2,
          setDragState: setDrag2,
          inputLabel: "Upload comparison image",
        })}
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