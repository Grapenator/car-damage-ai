import { useState } from "react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

// ---------- small helpers for diagram ----------

// Decide which area of the car a part belongs to
function mapPartToZone(part) {
  const id = (part.part_id || "").toLowerCase();
  const name = (part.part_name || "").toLowerCase();
  const text = `${id} ${name}`;

  const hasLeft = text.includes("left");
  const hasRight = text.includes("right");
  const hasFront = text.includes("front");
  const hasRear = text.includes("rear");

  // ---- Explicit rear stuff: trunk, hatch, quarter panel, rear bumper ----
  if (
    text.includes("trunk") ||
    text.includes("decklid") ||
    text.includes("tailgate") ||
    text.includes("hatch") ||
    text.includes("quarter panel") ||
    text.includes("quarter_panel")
  ) {
    return "rear";
  }

  if (text.includes("rear bumper")) {
    return "rear";
  }

  // ---- Side parts: doors, mirrors, rocker panel, side skirt ----
  const isSidePart =
    text.includes("door") ||
    text.includes("mirror") ||
    text.includes("rocker") ||
    text.includes("rocker panel") ||
    text.includes("side skirt") ||
    text.includes("side-skirt") ||
    text.includes("sideskirt");

  if (isSidePart) {
    // doors, mirrors, rocker, skirts ⇒ left/right side if we can tell
    if (hasLeft) return "left";
    if (hasRight) return "right";
    return "other";
  }

  // ---- Front parts: hood, radiator/core support, bumper, grille, headlights ----
  if (
    text.includes("hood") ||
    text.includes("radiator") ||
    text.includes("core support") ||
    text.includes("radiator support") ||
    text.includes("grille") ||
    text.includes("grill") ||
    text.includes("front bumper") ||
    text.includes("bumper cover") ||
    text.includes("headlight") ||
    text.includes("fog light") ||
    text.includes("foglight") ||
    text.includes("foglamp")
  ) {
    return "front";
  }

  // ---- Generic side zones (fenders, wheels, etc. that just say left/right) ----
  if (hasLeft) return "left";
  if (hasRight) return "right";

  // ---- Generic front/rear fallback ----
  if (hasRear) return "rear";
  if (hasFront) return "front";

  // Anything else (roof, glass, etc.)
  return "other";
}

function groupPartsByZone(parts) {
  const zones = {
    front: [],
    rear: [],
    left: [],
    right: [],
    other: [],
  };

  for (const p of parts) {
    const zone = mapPartToZone(p);
    zones[zone].push(p);
  }

  return zones;
}

// Card used inside diagram
function DiagramNode({ part }) {
  const severity = Number(part.severity) || 0;
  const total = Number(part.estimated_total_part_cost ?? 0);

  return (
    <div className={`diagram-node severity-${severity}`}>
      <div className="node-title">{part.part_name}</div>
      <div className="node-body">
        <span className="node-severity">Sev {severity}</span>
        {total > 0 && (
          <span className="node-cost">${total.toLocaleString()}</span>
        )}
      </div>
    </div>
  );
}

// ---------- main component ----------

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
  const zones = groupPartsByZone(parts);

  return (
    <div className="page-root">
      <div className="app">
        <header className="app-header">
          <h1>Car Damage Analyzer</h1>
          <p>
            Upload one or more photos of the <strong>same car</strong>. The AI
            will estimate damaged parts, severity, and repair costs, then log a
            report to Google Sheets.
          </p>
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
                  This helps the AI give more realistic parts and cost
                  estimates.
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
                      Selected {files.length} file
                      {files.length > 1 ? "s" : ""}:
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

              {parts.length > 0 && (
                <>
                  <h3 className="diagram-heading">Damage Diagram</h3>
                  <p className="hint">
                    Parts are grouped by where they sit on the car. Darker
                    borders mean higher severity.
                  </p>

                  <div className="diagram-layout">
                    <div className="diagram-zone zone-front">
                      <div className="zone-title">Front</div>
                      {zones.front.length === 0 ? (
                        <p className="zone-empty">No front damage</p>
                      ) : (
                        zones.front.map((p, i) => (
                          <DiagramNode key={`front-${i}`} part={p} />
                        ))
                      )}
                    </div>

                    <div className="diagram-zone zone-left">
                      <div className="zone-title">Left Side</div>
                      {zones.left.length === 0 ? (
                        <p className="zone-empty">No left-side damage</p>
                      ) : (
                        zones.left.map((p, i) => (
                          <DiagramNode key={`left-${i}`} part={p} />
                        ))
                      )}
                    </div>

                    <div className="diagram-center">
                      <span>Vehicle</span>
                    </div>

                    <div className="diagram-zone zone-right">
                      <div className="zone-title">Right Side</div>
                      {zones.right.length === 0 ? (
                        <p className="zone-empty">No right-side damage</p>
                      ) : (
                        zones.right.map((p, i) => (
                          <DiagramNode key={`right-${i}`} part={p} />
                        ))
                      )}
                    </div>

                    <div className="diagram-zone zone-rear">
                      <div className="zone-title">Rear</div>
                      {zones.rear.length === 0 ? (
                        <p className="zone-empty">No rear damage</p>
                      ) : (
                        zones.rear.map((p, i) => (
                          <DiagramNode key={`rear-${i}`} part={p} />
                        ))
                      )}
                    </div>

                    <div className="diagram-zone zone-other">
                      <div className="zone-title">Other / Unknown</div>
                      {zones.other.length === 0 ? (
                        <p className="zone-empty">None</p>
                      ) : (
                        zones.other.map((p, i) => (
                          <DiagramNode key={`other-${i}`} part={p} />
                        ))
                      )}
                    </div>
                  </div>
                </>
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
    </div>
  );
}

export default App;