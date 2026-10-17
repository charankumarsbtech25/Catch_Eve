import os
from pathlib import Path
from dotenv import load_dotenv
from qiskit_ibm_runtime import QiskitRuntimeService

load_dotenv(Path(__file__).resolve().parent / ".env")

api_key = os.getenv("IBM_QUANTUM_API_KEY")
crn = os.getenv("IBM_QUANTUM_CRN")

if not api_key:
    print("API key not found. Check your .env file.")
else:
    try:
        if crn:
            service = QiskitRuntimeService(
                channel="ibm_cloud",
                token=api_key,
                crn=crn,
            )
            print("IBM Quantum connected via IBM Cloud (CRN)!")
        else:
            service = QiskitRuntimeService(
                channel="ibm_quantum_platform",
                token=api_key,
            )
            print("IBM Quantum connected via IBM Quantum Platform!")
        print(service.backends())
    except Exception as error:  # noqa: BLE001
        print(f"Failed to connect to IBM Quantum: {error}")