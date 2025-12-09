import React from "react";

function DamageReportTable({ parts }) {
  if (!parts || parts.length === 0) {
    return <p>No damaged parts detected.</p>;
  }

  return (
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
            <tr key={part.part_id || idx}>
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
  );
}

export default DamageReportTable;