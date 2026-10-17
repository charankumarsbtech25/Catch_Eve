
from bb84_core import BB84Config, run_bb84


def display_results(result):
    """Display the BB84 simulation results."""

    print("\n" + "=" * 45)
    print("     BB84 QUANTUM KEY DISTRIBUTION")
    print("=" * 45)

    print("\n--- Simulation Settings ---")
    print("Qubits sent:", result.config.n_qubits)
    print("Eve interception:", f"{result.config.eve_fraction:.0%}")
    print("Channel noise:", f"{result.config.noise_p:.0%}")

    print("\n--- Communication Results ---")
    print("Matching bases:", len(result.sifted_indices))
    print("Sampled bits:", len(result.sample_indices))
    print(f"QBER: {result.qber:.2%}")
    print(
        "Abort threshold:",
        f"{result.config.abort_threshold:.0%}"
    )

    print("\n--- Security Status ---")
    if result.secure:
        print("Status: BELOW QBER ABORT THRESHOLD")
    else:
        print("Status: ABORT — QBER TOO HIGH")

    print("Final demonstration key length:", result.key_length)

    print("\n--- Message Demonstration ---")
    print("Original message:", result.config.message)
    print("Decrypted message:", result.decrypted)

    if result.ciphertext:
        print("Encrypted message bits:", len(result.ciphertext))
    else:
        print("Encrypted message: Not available")

    print("\n--- Quantum Simulation ---")
    print("Circuits executed:", result.total_circuits)
    print("Noise model enabled:", result.noise_model_used)
    print("Eve intercepted qubits:", sum(result.eve_present))

    print("\n--- Measurement Histogram ---")
    for label, counts in result.histogram.items():
        print(label, ":", counts)

    print("\n" + "=" * 45)


def main():
    print("Starting BB84 Quantum Key Distribution Simulator...")

    config = BB84Config(
        n_qubits=1000,
        eve_fraction=0.0,
        noise_p=0.0,
        seed=42,
        abort_threshold=0.11,
        sample_fraction=0.5,
        message="Hi Bob!"
    )

    try:
        result = run_bb84(config)
        display_results(result)

    except Exception as error:
        print("\nSimulation failed.")
        print("Error:", error)
        print(
            "Check your Qiskit installation and "
            "the contents of bb84_core.py."
        )


if __name__ == "__main__":
    main()
