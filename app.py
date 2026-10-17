
"""
Flask backend for the BB84 Quantum Key Distribution dashboard.

Endpoints:
  GET  /                 -> dashboard.html
  POST /api/run          -> Run BB84 simulation
  POST /api/sweep/eve    -> QBER vs Eve interception
  POST /api/sweep/noise  -> QBER vs channel noise
  GET  /api/health       -> Health check
"""

from dataclasses import asdict

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

import os
from pathlib import Path
from dotenv import load_dotenv
from qiskit_ibm_runtime import QiskitRuntimeService

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

IBM_API_KEY = os.getenv("IBM_QUANTUM_API_KEY")
IBM_QUANTUM_CRN = os.getenv("IBM_QUANTUM_CRN")



from bb84_core import (
    BB84Config,
    run_bb84,
    sweep_eve,
    sweep_noise,
)



app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
CORS(app)


def serialise_result(result):
    """Convert the simulation result into JSON-safe data."""
    data = asdict(result)

    # Keep the dashboard response reasonably small.
    for key in (
        "alice_bits",
        "alice_bases",
        "bob_bases",
        "bob_results",
        "eve_bases",
        "eve_results",
        "eve_present",
    ):
        data[key] = data[key][:40]

    data["ciphertext"] = data["ciphertext"][:512]

    return data


def read_json():
    """Read a JSON object from the request."""
    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")

    return body


def make_config(body):
    """Build and validate the simulation configuration."""
    try:
        config = BB84Config(
            n_qubits=int(body.get("n_qubits", 200)),
            eve_fraction=float(body.get("eve_fraction", 0.0)),
            noise_p=float(body.get("noise_p", 0.0)),
            seed=int(body.get("seed", 42)),
            abort_threshold=float(
                body.get("abort_threshold", 0.11)
            ),
            sample_fraction=float(
                body.get("sample_fraction", 0.5)
            ),
            message=str(body.get("message", "Hi Bob!")),
        )
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Invalid simulation configuration.")

    if not 1 <= config.n_qubits <= 1500:
        raise ValueError("n_qubits must be between 1 and 1500.")

    if not 0 <= config.eve_fraction <= 1:
        raise ValueError("eve_fraction must be between 0 and 1.")

    if not 0 <= config.noise_p <= 1:
        raise ValueError("noise_p must be between 0 and 1.")

    if not 0 <= config.abort_threshold <= 1:
        raise ValueError("abort_threshold must be between 0 and 1.")

    if not 0 < config.sample_fraction <= 1:
        raise ValueError("sample_fraction must be greater than 0 and at most 1.")

    if len(config.message.encode("utf-8")) > 256:
        raise ValueError("Message must be at most 256 UTF-8 bytes.")

    return config


@app.route("/")
def index():
    """Serve the dashboard page."""
    return render_template("dashboard.html")


@app.route("/api/health", methods=["GET"])
def health():
    """Check whether the Flask backend is running."""
    return jsonify({
        "status": "ok",
        "backend": "qiskit-aer",
        "message": "BB84 backend is running.",
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    """Run a complete BB84 simulation."""
    try:
        body = read_json()
        config = make_config(body)
        result = run_bb84(config)

        return jsonify(serialise_result(result))

    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        app.logger.exception("BB84 simulation failed")
        return jsonify({
            "error": "Simulation failed. Check the backend terminal."
        }), 500


@app.route("/api/sweep/eve", methods=["POST"])
def api_sweep_eve():
    """Measure QBER at different Eve interception fractions."""
    try:
        body = read_json()

        n_qubits = int(body.get("n_qubits", 150))
        noise_p = float(body.get("noise_p", 0.0))
        seed = int(body.get("seed", 42))

        if not 1 <= n_qubits <= 500:
            raise ValueError("Sweep n_qubits must be between 1 and 500.")

        if not 0 <= noise_p <= 1:
            raise ValueError("noise_p must be between 0 and 1.")

        data = sweep_eve(
            n_qubits=n_qubits,
            noise_p=noise_p,
            seed=seed,
        )

        return jsonify(data)

    except (TypeError, ValueError, OverflowError) as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        app.logger.exception("Eve sweep failed")
        return jsonify({"error": "Eve sweep failed."}), 500


@app.route("/api/sweep/noise", methods=["POST"])
def api_sweep_noise():
    """Measure QBER at different channel noise levels."""
    try:
        body = read_json()

        n_qubits = int(body.get("n_qubits", 150))
        eve_fraction = float(body.get("eve_fraction", 0.0))
        seed = int(body.get("seed", 42))

        if not 1 <= n_qubits <= 500:
            raise ValueError("Sweep n_qubits must be between 1 and 500.")

        if not 0 <= eve_fraction <= 1:
            raise ValueError("eve_fraction must be between 0 and 1.")

        data = sweep_noise(
            n_qubits=n_qubits,
            eve_fraction=eve_fraction,
            seed=seed,
        )

        return jsonify(data)

    except (TypeError, ValueError, OverflowError) as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        app.logger.exception("Noise sweep failed")
        return jsonify({"error": "Noise sweep failed."}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

# IBM Quantum Runtime is optional for the local simulator dashboard.
# Prefer the IBM Cloud environment (channel="ibm_cloud") using the CRN when
# available, falling back to the IBM Quantum Platform channel, and finally to
# simulator-only mode if no credentials are configured.
service = None
if IBM_API_KEY:
    try:
        if IBM_QUANTUM_CRN:
            service = QiskitRuntimeService(
                channel="ibm_cloud",
                token=IBM_API_KEY,
                crn=IBM_QUANTUM_CRN,
            )
            app.logger.info(
                "IBM Quantum Runtime service initialized via IBM Cloud (CRN)."
            )
        else:
            service = QiskitRuntimeService(
                channel="ibm_quantum_platform",
                token=IBM_API_KEY,
            )
            app.logger.info(
                "IBM Quantum Runtime service initialized via IBM Quantum Platform."
            )
    except Exception:  # noqa: BLE001 - keep the dashboard runnable offline
        app.logger.warning(
            "Could not initialize IBM Quantum Runtime service; "
            "running in simulator-only mode."
        )
else:
    app.logger.warning(
        "IBM_QUANTUM_API_KEY not set; running in simulator-only mode."
    )