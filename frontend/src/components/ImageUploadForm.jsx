import React from "react";

function ImageUploadForm({
  vehicleInfo,
  onVehicleInfoChange,
  files,
  isSubmitting,
  onFileChange,
  onClearFiles,
  onSubmit,
}) {
  return (
    <form onSubmit={onSubmit}>
      <div className="form-group">
        <label htmlFor="vehicleInfo">
          Vehicle year, make, and model (optional but recommended)
        </label>
        <input
          id="vehicleInfo"
          type="text"
          placeholder="e.g. 2006 Mitsubishi Lancer Evolution IX"
          value={vehicleInfo}
          onChange={(e) => onVehicleInfoChange(e.target.value)}
        />
        <p className="hint">
          This helps the AI give more realistic parts and cost estimates.
        </p>
      </div>

      <div className="form-group">
        <label htmlFor="fileInput">
          Images of your car (multiple angles recommended)
        </label>
        <p className="hint">
          You can select several photos at once. On some phones you may need to
          tap “Choose Images” multiple times to add more images.
        </p>
        <input
          id="fileInput"
          type="file"
          accept="image/*"
          multiple
          onChange={onFileChange}
        />
        {files.length > 0 && (
          <div className="selected-files">
            <p className="hint">
              Selected {files.length} file{files.length > 1 ? "s" : ""}:
            </p>
            <ul>
              {files.map((f) => (
                <li key={`${f.name}-${f.lastModified}`}>{f.name}</li>
              ))}
            </ul>
            <button
              type="button"
              className="secondary-button"
              onClick={onClearFiles}
              disabled={isSubmitting}
            >
              Clear images
            </button>
          </div>
        )}
      </div>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Analyzing..." : "Analyze Damage"}
      </button>
    </form>
  );
}

export default ImageUploadForm;