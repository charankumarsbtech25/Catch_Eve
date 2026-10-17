
"""
BB84 Quantum Key Distribution (QKD) Simulator Core
For the RV University Qiskit Hackathon.

Requirements:
    python -m pip install numpy qiskit qiskit-aer

This is an educational simulator, not production-secure QKD software.
"""

import random
import hashlib
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error
from qiskit.quantum_info import Statevector, state_fidelity


# ============================================================
# CONFIGURATION AND RESULTS
# ============================================================

@dataclass
class BB84Config:
    n_qubits: int = 200
    eve_fraction: float = 0.0
    noise_p: float = 0.0
    seed: Optional[int] = 42
    abort_threshold: float = 0.11
    sample_fraction: float = 0.5
    message: str = "Hi Bob!"


@dataclass
class BB84Result:
    alice_bits: list
    alice_bases: list
    bob_bases: list
    bob_results: list
    eve_bases: list
    eve_results: list
    eve_present: list
    sifted_indices: list
    sifted_alice: list
    sifted_bob: list
    sifted_eve_known: list
    sample_indices: list
    qber: float
    qber_std: float
    remaining_alice: list
    remaining_bob: list
    secure: bool
    final_key_alice: list
    final_key_bob: list
    key_length: int
    ciphertext: list
    decrypted: str
    config: BB84Config = field(default_factory=BB84Config)
    total_circuits: int = 0
    noise_model_used: bool = False
    circuit_diagram: str = ""
    fidelity_table: list = field(default_factory=list)
    histogram: dict = field(default_factory=dict)


# ============================================================
# QUANTUM CIRCUIT BUILDERS
# ============================================================

def build_alice_circuit(
    bit: int, basis: int, noise_p: float = 0.0
) -> QuantumCircuit:
    """
    Prepare a BB84 qubit.

    Basis 0: Z basis -> |0> or |1>
    Basis 1: X basis -> |+> or |->
    """
    if bit not in (0, 1) or basis not in (0, 1):
        raise ValueError("bit and basis must be 0 or 1")

    qc = QuantumCircuit(1, 1, name=f"A_{bit}{basis}")

    if basis == 0:
        if bit == 1:
            qc.x(0)
    else:
        if bit == 1:
            qc.x(0)
        qc.h(0)

    qc.barrier(label="quantum_channel")

    # The noise model applies depolarizing noise to this gate.
    if noise_p > 0:
        qc.id(0)

    return qc


def append_bob_measurement(
    qc: QuantumCircuit, basis: int
) -> QuantumCircuit:
    """Measure the qubit using Bob's chosen basis."""
    if basis not in (0, 1):
        raise ValueError("basis must be 0 or 1")

    if basis == 1:
        qc.h(0)

    qc.measure(0, 0)
    return qc


def build_noise_model(p: float) -> Optional[NoiseModel]:
    """Build a simple depolarizing noise model."""
    if not 0 <= p <= 1:
        raise ValueError("noise_p must be between 0 and 1")

    if p == 0:
        return None

    model = NoiseModel()
    model.add_all_qubit_quantum_error(
        depolarizing_error(p, 1), ["id"]
    )
    return model


def _simulate_one(
    circuit: QuantumCircuit,
    backend: AerSimulator,
    seed: Optional[int],
) -> int:
    """Run one circuit shot and return its measured bit."""
    compiled = transpile(
        circuit, backend, optimization_level=0
    )

    kwargs = {"shots": 1}
    if seed is not None:
        kwargs["seed_simulator"] = int(seed) % (2**32)

    counts = backend.run(compiled, **kwargs).result().get_counts()
    return int(next(iter(counts)))


# ============================================================
# BB84 SIMULATION PIPELINE
# ============================================================

def run_bb84(config: BB84Config) -> BB84Result:
    """Run the complete educational BB84 simulation."""

    if config.n_qubits < 1:
        raise ValueError("n_qubits must be at least 1")

    if not 0 <= config.eve_fraction <= 1:
        raise ValueError("eve_fraction must be between 0 and 1")

    if not 0 <= config.noise_p <= 1:
        raise ValueError("noise_p must be between 0 and 1")

    if not 0 < config.sample_fraction <= 1:
        raise ValueError("sample_fraction must be in (0, 1]")

    if not 0 <= config.abort_threshold <= 1:
        raise ValueError("abort_threshold must be between 0 and 1")

    rng = random.Random(config.seed)
    n = config.n_qubits

    noise_model = build_noise_model(config.noise_p)
    backend = AerSimulator(
        method="statevector",
        noise_model=noise_model,
    )

    # Step 1: Alice creates random bits and bases.
    alice_bits = [rng.randint(0, 1) for _ in range(n)]
    alice_bases = [rng.randint(0, 1) for _ in range(n)]

    # Step 2: Bob independently chooses measurement bases.
    bob_bases = [rng.randint(0, 1) for _ in range(n)]

    # Step 3: Determine which qubits Eve intercepts.
    eve_present = [
        rng.random() < config.eve_fraction for _ in range(n)
    ]
    eve_bases = [
        rng.randint(0, 1) if present else None
        for present in eve_present
    ]

    bob_results = [None] * n
    eve_results = [None] * n
    total_circuits = 0

    # Step 4: Transmit and measure each qubit.
    for i in range(n):
        circuit = build_alice_circuit(
            alice_bits[i],
            alice_bases[i],
            config.noise_p,
        )

        seed_i = None if config.seed is None else config.seed + i

        if eve_present[i]:
            # Eve intercepts and measures the qubit.
            eve_circuit = circuit.copy()

            if eve_bases[i] == 1:
                eve_circuit.h(0)

            eve_circuit.measure(0, 0)

            eve_bit = _simulate_one(
                eve_circuit, backend, seed_i
            )
            eve_results[i] = eve_bit
            total_circuits += 1

            # Eve prepares a replacement qubit using her result.
            bob_circuit = QuantumCircuit(1, 1)

            if eve_bases[i] == 0:
                if eve_bit == 1:
                    bob_circuit.x(0)
            else:
                if eve_bit == 1:
                    bob_circuit.x(0)
                bob_circuit.h(0)

            bob_circuit.barrier(label="eve_to_bob")

            if config.noise_p > 0:
                bob_circuit.id(0)

            if bob_bases[i] == 1:
                bob_circuit.h(0)

            bob_circuit.measure(0, 0)

            bob_seed = (
                None if config.seed is None
                else config.seed + i + 10000
            )

            bob_results[i] = _simulate_one(
                bob_circuit, backend, bob_seed
            )
            total_circuits += 1

        else:
            # Direct transmission from Alice to Bob.
            bob_circuit = append_bob_measurement(
                circuit.copy(), bob_bases[i]
            )

            bob_results[i] = _simulate_one(
                bob_circuit, backend, seed_i
            )
            total_circuits += 1

    # Step 5: Sift the key by keeping matching bases.
    sifted_indices = [
        i for i in range(n)
        if alice_bases[i] == bob_bases[i]
    ]

    sifted_alice = [
        alice_bits[i] for i in sifted_indices
    ]
    sifted_bob = [
        bob_results[i] for i in sifted_indices
    ]

    sifted_eve_known = [
        eve_present[i] and eve_bases[i] == alice_bases[i]
        for i in sifted_indices
    ]

    # Step 6: Estimate QBER using a random sample.
    n_sifted = len(sifted_indices)
    n_sample = (
        max(1, int(n_sifted * config.sample_fraction))
        if n_sifted else 0
    )

    sample_rng = random.Random(
        None if config.seed is None else config.seed + 50000
    )

    sample_positions = sorted(
        sample_rng.sample(
            range(n_sifted),
            min(n_sample, n_sifted),
        )
    )

    if sample_positions:
        mismatches = sum(
            sifted_alice[p] != sifted_bob[p]
            for p in sample_positions
        )
        qber = mismatches / len(sample_positions)
        qber_std = float(
            np.sqrt(
                qber * (1 - qber) / len(sample_positions)
            )
        )
    else:
        qber = 0.0
        qber_std = 0.0

    # Remove sampled positions from the remaining demonstration key.
    sample_set = set(sample_positions)

    remaining_alice = [
        sifted_alice[p] for p in range(n_sifted)
        if p not in sample_set
    ]
    remaining_bob = [
        sifted_bob[p] for p in range(n_sifted)
        if p not in sample_set
    ]

    # Step 7: Decide whether the measured QBER exceeds the threshold.
    secure = bool(
        n_sifted > 0
        and qber <= config.abort_threshold
    )

    # Step 8: Educational privacy-amplification demonstration.
    #
    # IMPORTANT:
    # This is NOT a full QKD privacy-amplification protocol.
    # It hashes Alice's remaining bits and copies the demonstration
    # key to Bob. A real protocol must reconcile and verify the keys
    # and use a proven privacy-amplification construction.
    final_key_alice = []
    final_key_bob = []

    if secure and len(remaining_alice) >= 8:
        alice_bytes = _bits_to_bytes(remaining_alice)

        digest = hashlib.sha256(alice_bytes).digest()

        h_q = 0.0
        if 0 < qber < 1:
            h_q = (
                -qber * np.log2(qber)
                - (1 - qber) * np.log2(1 - qber)
            )

        rate = max(0.0, 1 - 2 * h_q)
        safe_len = min(
            256,
            int(len(remaining_alice) * rate),
        )

        digest_bits = [
            (digest[j // 8] >> (7 - j % 8)) & 1
            for j in range(256)
        ]

        final_key_alice = digest_bits[:safe_len]
        final_key_bob = final_key_alice.copy()

    # Step 9: Demonstrate one-time-pad encryption.
    message_bits = _text_to_bits(config.message)
    key_len = len(final_key_alice)
    ciphertext = []

    if key_len >= len(message_bits) and key_len > 0:
        ciphertext = [
            m ^ k
            for m, k in zip(message_bits, final_key_alice)
        ]

        decrypted_bits = [
            c ^ k
            for c, k in zip(ciphertext, final_key_bob)
        ]
        decrypted = _bits_to_text(decrypted_bits)

    elif key_len >= 8:
        # Demonstrate only the whole-byte prefix the key can cover.
        usable_bits = (key_len // 8) * 8
        plaintext_prefix = message_bits[:usable_bits]

        ciphertext = [
            m ^ k
            for m, k in zip(
                plaintext_prefix,
                final_key_alice[:usable_bits],
            )
        ]

        decrypted_bits = [
            c ^ k
            for c, k in zip(
                ciphertext,
                final_key_bob[:usable_bits],
            )
        ]

        decrypted = (
            _bits_to_text(decrypted_bits) + " [truncated]"
        )
    else:
        decrypted = "[ABORTED — no usable key]"

    # Step 10: Produce a sample circuit diagram.
    diagram = ""
    if n > 0:
        sample_qc = build_alice_circuit(
            alice_bits[0],
            alice_bases[0],
            config.noise_p,
        )

        if eve_present[0]:
            if eve_bases[0] == 1:
                sample_qc.h(0)
            sample_qc.measure(0, 0)
        else:
            append_bob_measurement(sample_qc, bob_bases[0])

        diagram = str(sample_qc.draw(output="text"))

    # Step 11: Generate quantum-state fidelity and histogram data.
    fidelities = compute_state_fidelities()
    histogram = run_histogram_demo(
        n_shots=1000,
        seed=42 if config.seed is None else config.seed,
    )

    return BB84Result(
        alice_bits=alice_bits,
        alice_bases=alice_bases,
        bob_bases=bob_bases,
        bob_results=bob_results,
        eve_bases=eve_bases,
        eve_results=eve_results,
        eve_present=eve_present,
        sifted_indices=sifted_indices,
        sifted_alice=sifted_alice,
        sifted_bob=sifted_bob,
        sifted_eve_known=sifted_eve_known,
        sample_indices=sample_positions,
        qber=qber,
        qber_std=qber_std,
        remaining_alice=remaining_alice,
        remaining_bob=remaining_bob,
        secure=secure,
        final_key_alice=final_key_alice,
        final_key_bob=final_key_bob,
        key_length=len(final_key_alice),
        ciphertext=ciphertext,
        decrypted=decrypted,
        config=config,
        total_circuits=total_circuits,
        noise_model_used=noise_model is not None,
        circuit_diagram=diagram,
        fidelity_table=[
            {"pair": k, "fidelity": v}
            for k, v in fidelities.items()
        ],
        histogram=histogram,
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _text_to_bits(text: str) -> list:
    """Convert UTF-8 text into a list of bits."""
    return [
        (byte >> shift) & 1
        for byte in text.encode("utf-8")
        for shift in range(7, -1, -1)
    ]


def _bits_to_bytes(bits: list) -> bytes:
    """Convert complete groups of eight bits to bytes."""
    usable_length = (len(bits) // 8) * 8
    return bytes(
        int("".join(str(b) for b in bits[i:i + 8]), 2)
        for i in range(0, usable_length, 8)
    )


def _bits_to_text(bits: list) -> str:
    """Decode complete groups of eight bits as UTF-8."""
    raw = _bits_to_bytes(bits)
    return raw.decode("utf-8", errors="replace").rstrip("\x00")


def get_bloch_statevector(bit: int, basis: int) -> Statevector:
    """Return the statevector for one of the four BB84 states."""
    qc = QuantumCircuit(1)

    if basis == 0:
        if bit == 1:
            qc.x(0)
    elif basis == 1:
        if bit == 1:
            qc.x(0)
        qc.h(0)
    else:
        raise ValueError("basis must be 0 or 1")

    return Statevector.from_instruction(qc)


def compute_state_fidelities() -> dict:
    """Calculate pairwise fidelities for the four BB84 states."""
    states = {
        "|0>": get_bloch_statevector(0, 0),
        "|1>": get_bloch_statevector(1, 0),
        "|+>": get_bloch_statevector(0, 1),
        "|->": get_bloch_statevector(1, 1),
    }

    fidelities = {}

    for name_a, state_a in states.items():
        for name_b, state_b in states.items():
            fidelities[f"{name_a} vs {name_b}"] = round(
                float(state_fidelity(state_a, state_b)), 4
            )

    return fidelities


def run_histogram_demo(
    n_shots: int = 1000,
    seed: int = 42,
) -> dict:
    """Generate measurement histograms for |+> and |0>."""
    if n_shots < 1:
        raise ValueError("n_shots must be at least 1")

    backend = AerSimulator()
    results = {}

    # |+> measured in the Z basis should be approximately 50/50.
    qc_plus = QuantumCircuit(1, 1)
    qc_plus.h(0)
    qc_plus.measure(0, 0)

    results["|+> in Z"] = backend.run(
        transpile(qc_plus, backend),
        shots=n_shots,
        seed_simulator=seed,
    ).result().get_counts()

    # |0> measured in the Z basis should produce zero.
    qc_zero = QuantumCircuit(1, 1)
    qc_zero.measure(0, 0)

    results["|0> in Z"] = backend.run(
        transpile(qc_zero, backend),
        shots=n_shots,
        seed_simulator=seed,
    ).result().get_counts()

    return results


# ============================================================
# DATA FOR DASHBOARD CHARTS
# ============================================================

def sweep_eve(
    n_qubits: int = 30,
    noise_p: float = 0.0,
    seed: int = 42,
    points: int = 5,
) -> dict:
    """Run simulations at different Eve interception fractions."""
    if points < 2:
        raise ValueError("points must be at least 2")

    fractions = []
    qbers = []
    theoretical_qbers = []

    for i in range(points):
        fraction = i / (points - 1)

        config = BB84Config(
            n_qubits=n_qubits,
            eve_fraction=fraction,
            noise_p=noise_p,
            seed=seed,
        )

        result = run_bb84(config)

        fractions.append(fraction)
        qbers.append(round(result.qber, 4))

        # Ideal intercept-resend QBER is approximately 25% of
        # intercepted qubits, when evaluated over a large sample.
        theoretical_qbers.append(round(0.25 * fraction, 4))

    return {
        "eve_fraction": fractions,
        "qber": qbers,
        "theory_25pct": theoretical_qbers,
    }



def sweep_noise(
    n_qubits: int = 20,
    eve_fraction: float = 0.0,
    seed: int = 42,
    points: int = 5,
) -> dict:
    """Measure QBER across channel-noise levels."""
    if points < 2:
        raise ValueError("points must be at least 2")

    noise_levels = []
    qbers = []

    for i in range(points):
        noise_p = 0.2 * i / (points - 1)

        config = BB84Config(
            n_qubits=n_qubits,
            eve_fraction=eve_fraction,
            noise_p=noise_p,
            seed=seed + i,
        )

        result = run_bb84(config)

        noise_levels.append(round(noise_p, 3))
        qbers.append(round(result.qber, 4))

    return {
        "noise": noise_levels,
        "qber": qbers,
    }


# ============================================================
# OPTIONAL COMMAND-LINE TEST
# ============================================================

if __name__ == "__main__":
    config = BB84Config(
        n_qubits=1000,
        eve_fraction=0.0,
        noise_p=0.0,
        seed=42,
        message="Hi Bob!",
    )

    result = run_bb84(config)

    print("\n=== BB84 QUANTUM KEY DISTRIBUTION ===")
    print("Qubits sent:", config.n_qubits)
    print("Matching bases:", len(result.sifted_indices))
    print(f"QBER: {result.qber:.2%}")
    print("Below abort threshold:", result.secure)
    print("Final demonstration key length:", result.key_length)
    print("Decrypted message:", result.decrypted)
    print("Quantum circuits executed:", result.total_circuits)
