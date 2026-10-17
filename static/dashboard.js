
"use strict";

// BB84 dashboard client
const API = ""; // Same origin as Flask

const $ = (id) => document.getElementById(id);

const plotLayout = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#e6edf3", size: 11 },
  margin: { l: 45, r: 15, t: 15, b: 35 },
  xaxis: { gridcolor: "#30363d" },
  yaxis: { gridcolor: "#30363d" },
};

function showError(message) {
  const el = $("error-box");
  if (!el) {
    console.error(message);
    return;
  }
  el.textContent = message;
  el.style.display = "block";
}

function hideError() {
  const el = $("error-box");
  if (el) el.style.display = "none";
}


async function postJSON(url, body) {
  const response = await fetch(API + url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }

  return data;
}

// ------------------------------------------------------------
// Sidebar controls
// ------------------------------------------------------------

$("in-n").addEventListener("input", (event) => {
  $("lbl-n").textContent = event.target.value;
});

$("in-eve").addEventListener("input", (event) => {
  $("lbl-eve").textContent = event.target.value + "%";
});

$("in-noise").addEventListener("input", (event) => {
  $("lbl-noise").textContent = event.target.value + "%";
});

// ------------------------------------------------------------
// Backend health check
// ------------------------------------------------------------

async function checkBackend() {
  try {
    const response = await fetch(API + "/api/health");
    if (!response.ok) throw new Error("Backend unavailable");

    const data = await response.json();
    $("backend-status").textContent = "backend: " + data.backend;
  } catch {
    $("backend-status").textContent = "backend: offline";
  }
}

checkBackend();

// ------------------------------------------------------------
// Run the complete BB84 simulation
// ------------------------------------------------------------

$("btn-run").addEventListener("click", async () => {
  const body = {
    n_qubits: Number($("in-n").value),
    eve_fraction: Number($("in-eve").value) / 100,
    noise_p: Number($("in-noise").value) / 100,
    abort_threshold: Number($("in-abort").value),
    seed: Number($("in-seed").value),
    message: $("in-msg").value,
  };

  setBusy(true);
  hideError();

  try {
    const data = await postJSON("/api/run", body);
    renderResults(data);
  } catch (error) {
    showError("Simulation failed: " + error.message);
  } finally {
    setBusy(false);
  }
});

// ------------------------------------------------------------
// QBER versus Eve interception
// ------------------------------------------------------------

$("btn-sweep-eve").addEventListener("click", async () => {
  setBusy(true);
  hideError();

  try {
    const data = await postJSON("/api/sweep/eve", {
      // Sweep endpoint has a maximum of 500 qubits per run.
      n_qubits: 10,
      noise_p: Number($("in-noise").value) / 100,
      seed: Number($("in-seed").value),
    });

    Plotly.newPlot(
      "chart-sweep-eve",
      [
        {
          x: data.eve_fraction,
          y: data.qber,
          name: "Simulated",
          type: "scatter",
          mode: "lines+markers",
          line: { color: "#58a6ff" },
        },
        {
          x: data.eve_fraction,
          y: data.theory_25pct,
          name: "Ideal theory (25% × f)",
          type: "scatter",
          mode: "lines",
          line: { color: "#d29922", dash: "dash" },
        },
      ],
      {
        ...plotLayout,
        xaxis: {
          ...plotLayout.xaxis,
          title: "Eve interception fraction",
          tickformat: ".0%",
        },
        yaxis: {
          ...plotLayout.yaxis,
          title: "QBER",
          tickformat: ".0%",
        },
      },
      { displayModeBar: false, responsive: true }
    );
  } catch (error) {
    showError("Eve sweep failed: " + error.message);
  } finally {
    setBusy(false);
  }
});

// ------------------------------------------------------------
// QBER versus channel noise
// ------------------------------------------------------------

$("btn-sweep-noise").addEventListener("click", async () => {
  setBusy(true);
  hideError();

  try {
    const data = await postJSON("/api/sweep/noise", {
      n_qubits: Math.min(500, Number($("in-n").value)),
      eve_fraction: Number($("in-eve").value) / 100,
      seed: Number($("in-seed").value),
    });

    Plotly.newPlot(
      "chart-sweep-noise",
      [
        {
          x: data.noise,
          y: data.qber,
          name: "Simulated",
          type: "scatter",
          mode: "lines+markers",
          line: { color: "#58a6ff" },
        },
      ],
      {
        ...plotLayout,
        xaxis: {
          ...plotLayout.xaxis,
          title: "Depolarizing noise probability",
          tickformat: ".0%",
        },
        yaxis: {
          ...plotLayout.yaxis,
          title: "QBER",
          tickformat: ".0%",
        },
      },
      { displayModeBar: false, responsive: true }
    );
  } catch (error) {
    showError("Noise sweep failed: " + error.message);
  } finally {
    setBusy(false);
  }
});

// ------------------------------------------------------------
// Render simulation results
// ------------------------------------------------------------

function renderResults(data) {
  $("m-qber").textContent =
    `${(data.qber * 100).toFixed(2)}% ± ` +
    `${(data.qber_std * 100).toFixed(2)}%`;

  $("m-sifted").textContent = data.sifted_indices.length;
  $("m-key").textContent = data.key_length;

  const statusElement = $("m-status");
  statusElement.textContent = data.secure
    ? "BELOW THRESHOLD"
    : "ABORT";

  statusElement.className =
    "value " + (data.secure ? "status-secure" : "status-abort");

  // QBER chart
  Plotly.newPlot(
    "chart-qber",
    [
      {
        type: "bar",
        orientation: "h",
        y: ["QBER"],
        x: [data.qber],
        error_x: {
          type: "data",
          array: [data.qber_std],
        },
        marker: {
          color: data.secure ? "#3fb950" : "#f85149",
        },
      },
    ],
    {
      ...plotLayout,
      xaxis: {
        ...plotLayout.xaxis,
        range: [0, 0.35],
        tickformat: ".0%",
      },
      shapes: [
        {
          type: "line",
          x0: data.config.abort_threshold,
          x1: data.config.abort_threshold,
          y0: -0.5,
          y1: 0.5,
          line: { color: "#f85149", dash: "dash", width: 2 },
        },
      ],
      annotations: [
        {
          x: data.config.abort_threshold,
          y: 0.55,
          text: `Abort threshold: ${
            (data.config.abort_threshold * 100).toFixed(1)
          }%`,
          showarrow: false,
          font: { color: "#f85149", size: 10 },
        },
      ],
    },
    { displayModeBar: false, responsive: true }
  );

  // Key sifting funnel
  Plotly.newPlot(
    "chart-funnel",
    [
      {
        type: "bar",
        orientation: "h",
        y: [
          "Sent",
          "Sifted",
          "After QBER sample",
          "Final key",
        ],
        x: [
          data.config.n_qubits,
          data.sifted_indices.length,
          data.remaining_alice.length,
          data.key_length,
        ],
        marker: { color: "#58a6ff" },
      },
    ],
    {
      ...plotLayout,
      xaxis: { ...plotLayout.xaxis, title: "Bits" },
    },
    { displayModeBar: false, responsive: true }
  );

  // Quantum circuit diagram
  $("circuit-diagram").textContent =
    data.circuit_diagram || "(No circuit diagram available)";

  // Measurement histogram
  const histogramTraces = [];
  const colors = {
    "|+> in Z": "#58a6ff",
    "|0> in Z": "#3fb950",
  };

  for (const [label, counts] of Object.entries(data.histogram || {})) {
    const keys = Object.keys(counts).sort();

    histogramTraces.push({
      x: keys,
      y: keys.map((key) => counts[key]),
      name: label,
      type: "bar",
      marker: { color: colors[label] || "#8b949e" },
    });
  }

  Plotly.newPlot(
    "chart-histogram",
    histogramTraces,
    { ...plotLayout, barmode: "group" },
    { displayModeBar: false, responsive: true }
  );

  // State fidelity table
  const fidelityTable = $("fidelity-table");

  fidelityTable.querySelector("thead").innerHTML =
    "<tr><th>Pair</th><th>Fidelity</th></tr>";

  fidelityTable.querySelector("tbody").innerHTML =
    (data.fidelity_table || [])
      .map(
        (row) =>
          `<tr>
             <td>${escapeHTML(row.pair)}</td>
             <td>${Number(row.fidelity).toFixed(4)}</td>
           </tr>`
      )
      .join("");

  // Protocol table (first 40 qubits returned by backend)
  const protocolTable = $("protocol-table");

  protocolTable.querySelector("thead").innerHTML =
    "<tr><th>#</th><th>Alice bit</th><th>Alice basis</th>" +
    "<th>Eve</th><th>Eve basis</th><th>Eve result</th>" +
    "<th>Bob basis</th><th>Bob result</th><th>Match</th></tr>";

  protocolTable.querySelector("tbody").innerHTML =
    data.alice_bits
      .map((aliceBit, index) => {
        const matchingBasis =
          data.alice_bases[index] === data.bob_bases[index];

        const evePresent = data.eve_present[index];
        const eveBasis = data.eve_bases[index];
        const eveResult = data.eve_results[index];

        return `
          <tr>
            <td>${index}</td>
            <td>${aliceBit}</td>
            <td>${data.alice_bases[index] === 0 ? "Z" : "X"}</td>
            <td class="${evePresent ? "eve-yes" : ""}">
              ${evePresent ? "Yes" : "—"}
            </td>
            <td>
              ${eveBasis == null ? "—" : eveBasis === 0 ? "Z" : "X"}
            </td>
            <td>${eveResult == null ? "—" : eveResult}</td>
            <td>${data.bob_bases[index] === 0 ? "Z" : "X"}</td>
            <td>${data.bob_results[index] ?? "—"}</td>
            <td class="${matchingBasis ? "match-yes" : "match-no"}">
              ${matchingBasis ? "Yes" : "No"}
            </td>
          </tr>
        `;
      })
      .join("");

  // One-time-pad educational demonstration
  $("otp-msg").textContent = data.config.message;
  $("otp-dec").textContent = data.decrypted;

  $("otp-meta").textContent =
    `Key bits used: ${data.ciphertext.length} · ` +
    `Qiskit circuits: ${data.total_circuits} · ` +
    `Noise model active: ${data.noise_model_used}`;
}

// Escape text before placing it in an HTML table.
function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

// ------------------------------------------------------------
// Busy indicator
// ------------------------------------------------------------

function setBusy(isBusy) {
  $("btn-run").disabled = isBusy;

  const spinner = $("spinner");
  if (spinner) {
    spinner.classList.toggle("active", isBusy);
  }

  if (isBusy) hideError();
}
