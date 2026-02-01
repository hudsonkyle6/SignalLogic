import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple

class ProofRFIGate:
    def __init__(self, seed: int = 20260122):
        self.N = 64
        self.dt = 0.01
        self.steps = 500
        self.threshold = 0.75
        self.tau_hold = 20
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        self.omega = np.concatenate([
            np.full(21, 1.0),
            np.full(22, 0.5),
            np.full(21, 2/3)
        ])

        self.K = np.zeros((self.N, self.N))
        self.K[0:21, 0:21] = 0.8
        self.K[21:43, 21:43] = 0.8
        self.K[43:, 43:] = 0.8
        np.fill_diagonal(self.K, 0.0)  # no self-coupling

    def coherence(self, theta: np.ndarray) -> float:
        return float(np.abs(np.mean(np.exp(1j * theta))))

    def run_dynamics(self, theta_init: np.ndarray) -> Tuple[List[float], float]:
        theta = theta_init.copy() % (2*np.pi)
        r_traj = [self.coherence(theta)]

        for _ in range(self.steps):
            sin_diff = np.sin(theta[None, :] - theta[:, None])     # θ_j - θ_i
            coupling = (self.K * sin_diff).sum(axis=1) / self.N    # Σ_j K_ij sin(...) / N
            dtheta = self.omega + coupling
            theta = (theta + self.dt * dtheta) % (2*np.pi)
            r_traj.append(self.coherence(theta))

        return r_traj, r_traj[-1]

    def gate(self, perturbation: np.ndarray, initial_aligned: bool = False) -> Tuple[str, float, List[float]]:
        if initial_aligned:
            theta_init = np.full(self.N, 1.0) + perturbation
        else:
            theta_init = self.rng.uniform(0, 2*np.pi, self.N) + perturbation

        r_traj, r_final = self.run_dynamics(theta_init)

        tail = r_traj[-self.tau_hold:]
        persisted = (len(tail) == self.tau_hold) and all(r >= self.threshold for r in tail)

        decision = "SPEAK" if (r_final >= self.threshold and persisted) else "SILENCE"
        return decision, r_final, r_traj


def run_proof_test(gate: ProofRFIGate, name: str, perturbation: np.ndarray, initial_aligned: bool):
    print(f"\n=== Proof Test: {name} ===")
    decision, r_final, r_traj = gate.gate(perturbation, initial_aligned)
    print(f"Decision: {decision}")
    print(f"Final r: {r_final:.4f}")
    print(f"Tail (last {gate.tau_hold}): {[round(r,4) for r in r_traj[-gate.tau_hold:]]}")

    plt.figure(figsize=(8,4))
    plt.plot(r_traj, label="r(t)")
    plt.axhline(gate.threshold, color="r", linestyle="--", label="threshold")
    plt.title(f"{name} — r(t)")
    plt.xlabel("Steps")
    plt.ylabel("r")
    plt.legend()
    plt.grid(True)
    plt.savefig(f"{name.replace(' ', '_')}_r_plot.png")
    plt.close()


if __name__ == "__main__":
    gate = ProofRFIGate(seed=20260122)

    # Test 1: coherent perturbation aligned to cluster A only
    coherent_pert = np.zeros(gate.N)
    coherent_pert[:21] = np.linspace(0, 0.2, 21)
    run_proof_test(gate, "Coherent Input", coherent_pert, initial_aligned=True)

    # Test 2: incoherent (random initial), no structured perturbation needed
    incoherent_pert = np.zeros(gate.N)
    run_proof_test(gate, "Incoherent Input", incoherent_pert, initial_aligned=False)

    print("\nDone. Check saved plots for r(t) trajectories.")
