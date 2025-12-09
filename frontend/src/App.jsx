import { useState } from "react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function App() {
  const [files, setFiles] = useState([]);
  const [vehicleInfo, setVehicleInfo] = useState(""); // year / make / model
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null); // holds backend JSON

  const handleFileChange = (event) => {
    setError("");
    setResult(null);

    const selected = Array.from(event.target.files || []);

    setFiles((prev) => {
      // avoid exact duplicates (same name + lastModified)
      const existingKeys = new Set(
        prev.map((f) => `${f.name}-${f.lastModified}`)
      );
      const merged = [...prev];

      for (const file of selected) {
        const key = `${file.name}-${file.lastModified}`;
        if (!existingKeys.has(key)) {
          merged.push(file);
        }
      }

      return merged;
    });

    // reset the input so picking the same file again will fire onChange
    event.target.value = "";
  };

  const handleClearFiles = () => {
    setFiles([]);
    setResult(null);
    setError("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setResult(null);

    if (!files || files.length === 0) {
      setError("Please select at least one image of your car.");
      return;
    }

    const formData = new FormData();
    files.forEach((file) => {
      // field name must match FastAPI parameter: files: List[UploadFile]
      formData.append("files", file);
    });

    // optional vehicle_info field for the backend
    if (vehicleInfo.trim()) {
      formData.append("vehicle_info", vehicleInfo.trim());
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        // Try to parse JSON error
        let detail = `Request failed with status ${response.status}`;
        try {
          const errJson = await response.json();
          if (errJson.detail) {
            detail =
              typeof errJson.detail === "string"
                ? errJson.detail
                : JSON.stringify(errJson.detail);
          }
        } catch {
          // ignore JSON parse error
        }
        throw new Error(detail);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      console.error("Analyze error:", err);
      setError(err.message || "Unexpected error while analyzing damage.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const overallCost =
    result?.damage_report?.overall_estimated_repair_cost ?? null;
  const parts = result?.damage_report?.parts ?? [];

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <h1>Car Damage Analyzer</h1>
          <p>
            Upload one or more photos of the <strong>same car</strong>. The AI
            will estimate damaged parts, severity, and repair costs, then log a
            report to Google Sheets.
          </p>
        </div>
      </header>

      <main className="app-main">
        <section className="card">
          <h2>Upload images</h2>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="vehicleInfo">
                Vehicle year, make, and model (optional but recommended)
              </label>
              <input
                id="vehicleInfo"
                type="text"
                placeholder="e.g. 2006 Mitsubishi Lancer Evolution IX"
                value={vehicleInfo}
                onChange={(e) => setVehicleInfo(e.target.value)}
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
                You can select several photos at once. On some phones you may
                need to tap “Choose Files” multiple times to add more images.
              </p>
              <input
                id="fileInput"
                type="file"
                accept="image/*"
                multiple
                onChange={handleFileChange}
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
                    onClick={handleClearFiles}
                    disabled={isSubmitting}
                  >
                    Clear files
                  </button>
                </div>
              )}
            </div>

            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Analyzing..." : "Analyze Damage"}
            </button>
          </form>

          {error && <div className="error">Error: {error}</div>}
        </section>

        {result && (
          <section className="card">
            <h2>Damage Report</h2>

            <div className="summary">
              <p>
                <strong>Report ID:</strong> {result.report_id}
              </p>
              <p>
                <strong>Notes:</strong> {result.damage_report?.notes}
              </p>
              {overallCost !== null && (
                <p>
                  <strong>Overall Estimated Repair Cost:</strong>{" "}
                  ${Number(overallCost).toLocaleString()}
                </p>
              )}
            </div>

            <h3>Damaged Parts</h3>
            {parts.length === 0 ? (
              <p>No damaged parts detected.</p>
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Part Name</th>
                      <th>Description</th>
                      <th>Severity (1–5)</th>
                      <th>Material Cost ($)</th>
                      <th>Paint Cost ($)</th>
                      <th>Structural Cost ($)</th>
                      <th>Total Part Cost ($)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parts.map((part, idx) => (
                      <tr key={idx}>
                        <td>{part.part_name}</td>
                        <td>{part.damage_description}</td>
                        <td>{part.severity}</td>
                        <td>{part.estimated_material_cost}</td>
                        <td>{part.estimated_paint_cost}</td>
                        <td>{part.estimated_structural_cost}</td>
                        <td>{part.estimated_total_part_cost}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {result.sheet_url && (
              <div className="sheet-link">
                <a
                  href={result.sheet_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open full report in Google Sheets
                </a>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;