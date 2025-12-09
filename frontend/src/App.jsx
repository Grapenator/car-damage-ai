import { useState } from "react";
import "./App.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function App() {
  const [files, setFiles] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null); // holds backend JSON

  const handleFileChange = (event) => {
    setError("");
    setResult(null);
    const selected = Array.from(event.target.files || []);
    setFiles(selected);
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
            detail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
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
        <h1>Car Damage Analyzer</h1>
        <p>
          Upload one or more photos of the <strong>same car</strong>. The AI will
          estimate damaged parts, severity, and repair costs, then log a report to
          Google Sheets.
        </p>
      </header>

      <main className="app-main">
        <section className="card">
          <h2>Upload images</h2>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="fileInput">
                Images of your car (multiple angles recommended)
              </label>
              <input
                id="fileInput"
                type="file"
                accept="image/*"
                multiple
                onChange={handleFileChange}
              />
              {files.length > 0 && (
                <p className="hint">
                  Selected {files.length} file{files.length > 1 ? "s" : ""}.
                </p>
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
                  ${overallCost.toLocaleString()}
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
                      <th>Labor Hours</th>
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
                        <td>{part.estimated_labor_hours}</td>
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