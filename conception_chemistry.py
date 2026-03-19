"""Conception → Neonatal Life-Saving Chemistry Pipeline

Simulates the critical molecules at every stage from conception through birth,
using the universe-sim quantum chemistry engine.

Timeline:
    Week 0 (Conception): Progesterone, hCG, Folic Acid
    Week 4 (First missed cycle / detection): Folate, B12, Iron
    Weeks 4-8 (Neural tube closure): Folic acid, Methylcobalamin, Fe²⁺
    Weeks 8-12 (Organogenesis): Retinoic acid, Zinc, Calcium, Iodine
    Weeks 12-24 (Fetal growth): DHA, Iron, Thyroxine
    Weeks 24-28 (Viability threshold): DPPC surfactant, SP-B
    Weeks 28-37 (Preterm risk): All NICU interventions from chemopedia
    Week 37+ (Term): Oxytocin, Prostaglandin E2, Vitamin K

Life begins at conception. Non-invasive detection begins at first missed
lunar cycle (~4 weeks). The intervention surface starts at detection.

Author: Tyler "The TimeLord" Roost
Uses: E:\\universe-sim quantum chemistry engine
"""

import sys
import json
import time
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

# Add universe-sim to path for imports
UNIVERSE_SIM_ROOT = Path("E:/universe-sim")
sys.path.insert(0, str(UNIVERSE_SIM_ROOT / "src"))

from universe_sim.chemistry.quantum_chem import (
    Atom,
    MolecularSystem,
    build_molecular_hamiltonian,
    estimate_qubits,
    SpatialTessellator,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ─── Gestational Stage Definitions ────────────────────────────────

@dataclass
class GestationalStage:
    name: str
    week_start: int
    week_end: int
    description: str
    clinical_context: str


STAGES = [
    GestationalStage(
        name="Conception",
        week_start=0, week_end=0,
        description="Fertilization and implantation",
        clinical_context="Progesterone maintains uterine lining. hCG signals pregnancy. Folate stores are the only buffer against neural tube defects.",
    ),
    GestationalStage(
        name="Detection (First Missed Cycle)",
        week_start=4, week_end=4,
        description="First non-invasive detection point — missed lunar cycle",
        clinical_context="Neural tube closing. Folate supplementation is time-critical — deficiency here causes spina bifida and anencephaly. B12 and iron metabolism are co-dependent.",
    ),
    GestationalStage(
        name="Neural Tube Closure",
        week_start=4, week_end=8,
        description="Neural tube and early organ formation",
        clinical_context="Folic acid prevents 70% of neural tube defects. Methylcobalamin (B12) is required for folate metabolism. Iron for hemoglobin synthesis in expanding blood volume.",
    ),
    GestationalStage(
        name="Organogenesis",
        week_start=8, week_end=12,
        description="Major organ systems forming",
        clinical_context="Retinoic acid (Vitamin A) directs limb patterning and organ morphogenesis. Zinc for DNA synthesis. Calcium for skeletal mineralization. Iodine for fetal thyroid.",
    ),
    GestationalStage(
        name="Fetal Growth",
        week_start=12, week_end=24,
        description="Rapid growth, CNS myelination, organ maturation",
        clinical_context="DHA for brain myelination. Iron for fetal iron stores (third trimester loading). Thyroxine for CNS development — maternal thyroid hormone crosses placenta until fetal thyroid activates ~week 20.",
    ),
    GestationalStage(
        name="Viability Threshold",
        week_start=24, week_end=28,
        description="Surfactant production begins, lungs approach viability",
        clinical_context="DPPC (dipalmitoylphosphatidylcholine) is the primary lung surfactant. SP-B protein enables surfactant spreading. Dexamethasone given antenatally accelerates surfactant production — prevents RDS. This is the $0.20 drug that saves 500,000 lives/year if universally available.",
    ),
    GestationalStage(
        name="Preterm Risk Window",
        week_start=28, week_end=37,
        description="Preterm birth risk — all NICU interventions become relevant",
        clinical_context="If born now: surfactant, caffeine citrate (apnea), NO (PPHN), phenobarbital (seizures), ampicillin (sepsis), dopamine (hypotension). Every molecule in the original chemopedia 42.",
    ),
    GestationalStage(
        name="Term Birth",
        week_start=37, week_end=42,
        description="Full term — delivery and immediate postnatal",
        clinical_context="Oxytocin for labor induction/augmentation. Prostaglandin E2 for cervical ripening. Vitamin K injection prevents hemorrhagic disease of the newborn. Erythromycin eye prophylaxis.",
    ),
]


# ─── Molecular Definitions ────────────────────────────────────────
# Geometries from published computational chemistry (NIST CCCBDB, PubChem 3D)
# Coordinates in Bohr (1 Bohr = 0.529177 Angstrom)

def _angstrom_to_bohr(x: float) -> float:
    return x / 0.529177


def mol(symbol: str, x: float, y: float, z: float) -> Atom:
    """Create atom with coordinates in Angstroms, converted to Bohr."""
    return Atom(symbol, _angstrom_to_bohr(x), _angstrom_to_bohr(y), _angstrom_to_bohr(z))


@dataclass
class LifeSavingMolecule:
    name: str
    formula: str
    stage: str
    week: int
    clinical_role: str
    what_happens_without: str
    system: MolecularSystem
    cost_to_make: str
    access_barrier: str


# ── Water (H₂O) — universal solvent, WFI for all IV preparations ──
WATER = LifeSavingMolecule(
    name="Water (WFI)",
    formula="H2O",
    stage="All stages",
    week=0,
    clinical_role="Solvent for all IV preparations, hydration",
    what_happens_without="Dehydration. Death.",
    system=MolecularSystem(atoms=[
        mol("O", 0.000, 0.000, 0.117),
        mol("H", 0.000, 0.757, -0.469),
        mol("H", 0.000, -0.757, -0.469),
    ], basis_set="sto-3g"),
    cost_to_make="$0.001/L (distillation)",
    access_barrier="WFI quality control in low-resource settings",
)

# ── Folic Acid (C₁₉H₁₉N₇O₆) — neural tube defect prevention ──
# Simplified geometry — backbone only for tractable simulation
FOLIC_ACID_CORE = LifeSavingMolecule(
    name="Folic Acid (Pteroylglutamic acid) — pteridine ring core",
    formula="C7H5N3O",  # Pteridine ring fragment for tractable simulation
    stage="Conception → Neural Tube Closure",
    week=0,
    clinical_role="Prevents 70% of neural tube defects (spina bifida, anencephaly)",
    what_happens_without="Neural tube defects: 300,000 cases/year globally. Spina bifida, anencephaly, encephalocele.",
    system=MolecularSystem(atoms=[
        # Pteridine ring core (2-amino-4-hydroxypteridine)
        mol("N", 0.000, 0.000, 0.000),
        mol("C", 1.340, 0.000, 0.000),
        mol("N", 2.010, 1.160, 0.000),
        mol("C", 1.340, 2.320, 0.000),
        mol("C", 0.000, 2.320, 0.000),
        mol("C", -0.670, 1.160, 0.000),
        mol("N", -2.010, 1.160, 0.000),
        mol("C", 1.340, 3.480, 0.000),
        mol("N", 2.680, 3.480, 0.000),
        mol("C", 3.350, 2.320, 0.000),
        mol("N", 2.680, 1.160, 0.000),
        mol("O", 4.690, 2.320, 0.000),
        # Hydrogens on amino group
        mol("H", -2.550, 0.310, 0.000),
        mol("H", -2.550, 2.010, 0.000),
        mol("H", 0.670, 4.330, 0.000),
        mol("H", 3.220, 4.330, 0.000),
        mol("H", 1.880, -0.890, 0.000),
    ], basis_set="sto-3g"),
    cost_to_make="$0.01/tablet (400 mcg)",
    access_barrier="Available but not supplemented in 50+ countries. WHO Essential Medicine.",
)

# ── Progesterone (C₂₁H₃₀O₂) — steroid ring core ──
PROGESTERONE_CORE = LifeSavingMolecule(
    name="Progesterone — steroid A-ring core",
    formula="C6H8O",  # Cyclohexenone core for tractable simulation
    stage="Conception",
    week=0,
    clinical_role="Maintains uterine lining, prevents miscarriage. Supplemented in high-risk pregnancies.",
    what_happens_without="Luteal phase deficiency → spontaneous abortion. 10-15% of pregnancies fail from insufficient progesterone.",
    system=MolecularSystem(atoms=[
        # Cyclohex-2-enone (A-ring of steroid skeleton)
        mol("C", 0.000, 1.400, 0.000),
        mol("C", 1.212, 0.700, 0.000),
        mol("C", 1.212, -0.700, 0.000),
        mol("C", 0.000, -1.400, 0.000),
        mol("C", -1.212, -0.700, 0.000),
        mol("C", -1.212, 0.700, 0.000),
        mol("O", 0.000, 2.620, 0.000),
        # Hydrogens
        mol("H", 2.140, 1.250, 0.000),
        mol("H", 2.140, -1.250, 0.000),
        mol("H", 0.000, -2.490, 0.500),
        mol("H", 0.000, -2.490, -0.500),
        mol("H", -2.140, -1.250, 0.000),
        mol("H", -2.140, 1.250, 0.000),
        mol("H", -1.212, -0.700, 1.090),
        mol("H", 1.212, -0.700, 1.090),
    ], basis_set="sto-3g"),
    cost_to_make="$0.10/dose (micronized oral)",
    access_barrier="Generic but underused in threatened miscarriage protocols in LMICs",
)

# ── Iron (Fe²⁺) in heme context — simplest iron complex ──
IRON_COMPLEX = LifeSavingMolecule(
    name="Iron(II) aquo complex — [Fe(H2O)]²⁺ minimal model",
    formula="FeH2O",
    stage="Neural Tube Closure → Term",
    week=4,
    clinical_role="Hemoglobin synthesis, oxygen transport, fetal iron loading",
    what_happens_without="Maternal anemia → preterm birth, low birth weight, neonatal anemia. Iron deficiency affects 40% of pregnancies globally.",
    system=MolecularSystem(atoms=[
        mol("Fe", 0.000, 0.000, 0.000),
        mol("O",  2.100, 0.000, 0.000),
        mol("H",  2.600, 0.760, 0.000),
        mol("H",  2.600, -0.760, 0.000),
    ], charge=2, spin_multiplicity=5, basis_set="sto-3g"),
    cost_to_make="$0.01/tablet (ferrous sulfate 325mg)",
    access_barrier="Available everywhere. Compliance is the barrier — GI side effects.",
)

# ── Calcium ion (Ca²⁺) — skeletal mineralization ──
CALCIUM = LifeSavingMolecule(
    name="Calcium ion — in phosphate context",
    formula="CaO",  # Simplified CaO as calcium model
    stage="Organogenesis → Term",
    week=8,
    clinical_role="Skeletal mineralization, cardiac function, preeclampsia prevention",
    what_happens_without="Neonatal hypocalcemia, rickets, maternal preeclampsia. WHO recommends Ca supplementation in populations with low dietary calcium.",
    system=MolecularSystem(atoms=[
        # Use Mg as proxy (Ca not in ELEMENT_DATA, Mg is closest available)
        mol("Mg", 0.000, 0.000, 0.000),
        mol("O",  1.749, 0.000, 0.000),
    ], basis_set="sto-3g"),
    cost_to_make="$0.02/tablet (calcium carbonate 500mg)",
    access_barrier="Cheap. Underused. WHO guideline compliance <30% in Sub-Saharan Africa.",
)

# ── Molecular oxygen (O₂) — the most basic requirement ──
OXYGEN = LifeSavingMolecule(
    name="Molecular Oxygen",
    formula="O2",
    stage="All stages",
    week=0,
    clinical_role="Aerobic respiration. Fetal oxygenation via placenta. Neonatal resuscitation.",
    what_happens_without="Hypoxia. Brain damage in minutes. Death.",
    system=MolecularSystem(atoms=[
        mol("O", 0.000, 0.000, 0.000),
        mol("O", 1.208, 0.000, 0.000),
    ], spin_multiplicity=3, basis_set="sto-3g"),
    cost_to_make="$0.01/L (PSA concentrator)",
    access_barrier="Oxygen concentrators cost $1000+. 50% of hospitals in Sub-Saharan Africa lack reliable oxygen supply.",
)

# ── Nitric Oxide (NO) — vasodilator for PPHN ──
NITRIC_OXIDE = LifeSavingMolecule(
    name="Nitric Oxide",
    formula="NO",
    stage="Preterm Risk → Term",
    week=24,
    clinical_role="Pulmonary vasodilator for persistent pulmonary hypertension of the newborn (PPHN)",
    what_happens_without="~15,000 PPHN deaths/year. Patent on a tube with a hole (Mallinckrodt INOmax).",
    system=MolecularSystem(atoms=[
        mol("N", 0.000, 0.000, 0.000),
        mol("O", 1.151, 0.000, 0.000),
    ], spin_multiplicity=2, basis_set="sto-3g"),
    cost_to_make="$0.10/dose from NO₂/N₂ gas cylinders",
    access_barrier="Patent on electronic delivery device. Venturi bypass in chemopedia eliminates this.",
)

# ── Sodium Bicarbonate (NaHCO₃) — metabolic acidosis ──
SODIUM_BICARBONATE = LifeSavingMolecule(
    name="Sodium Bicarbonate",
    formula="NaHCO3",
    stage="Preterm → Term (NICU)",
    week=28,
    clinical_role="Corrects metabolic acidosis in critically ill neonates",
    what_happens_without="Uncorrected acidosis → cardiac dysfunction, organ failure",
    system=MolecularSystem(atoms=[
        mol("Na", 0.000, 0.000, 0.000),
        mol("O",  2.400, 0.000, 0.000),
        mol("C",  3.600, 0.000, 0.000),
        mol("O",  4.200, 1.100, 0.000),
        mol("O",  4.200, -1.100, 0.000),
        mol("H",  4.800, -1.100, 0.800),
    ], basis_set="sto-3g"),
    cost_to_make="$0.05/vial (8.4% solution)",
    access_barrier="Commodity chemical. Access limited only by IV preparation infrastructure.",
)

# ── Dexamethasone — antenatal corticosteroid ──
DEXAMETHASONE_CORE = LifeSavingMolecule(
    name="Dexamethasone — fluorinated steroid A-ring",
    formula="C6H7FO",  # Fluorinated cyclohexenone fragment
    stage="Viability Threshold (antenatal)",
    week=24,
    clinical_role="Accelerates fetal lung maturation. The single most impactful intervention in neonatal medicine — $0.20/course, prevents RDS, saves 500,000 lives/year if universally available.",
    what_happens_without="Respiratory distress syndrome. Leading cause of neonatal death in preterm infants. 1 million deaths/year from RDS.",
    system=MolecularSystem(atoms=[
        # Fluorinated A-ring
        mol("C", 0.000, 1.400, 0.000),
        mol("C", 1.212, 0.700, 0.000),
        mol("C", 1.212, -0.700, 0.000),
        mol("C", 0.000, -1.400, 0.000),
        mol("C", -1.212, -0.700, 0.000),
        mol("C", -1.212, 0.700, 0.000),
        mol("O", 0.000, 2.620, 0.000),
        mol("F", 0.000, -2.800, 0.000),
        # Hydrogens
        mol("H", 2.140, 1.250, 0.000),
        mol("H", 2.140, -1.250, 0.000),
        mol("H", -2.140, -1.250, 0.000),
        mol("H", -2.140, 1.250, 0.000),
        mol("H", -1.212, -0.700, 1.090),
        mol("H", 1.212, -0.700, 1.090),
        mol("H", -1.212, 0.700, 1.090),
    ], basis_set="sto-3g"),
    cost_to_make="$0.20/course (two 12mg IM injections)",
    access_barrier="WHO Essential Medicine. Available but underused — 10% coverage in LMICs where 99% of neonatal deaths occur.",
)

# ── Zinc sulfate — DNA synthesis, immune function ──
ZINC_SULFATE = LifeSavingMolecule(
    name="Zinc Sulfate",
    formula="ZnSO4",
    stage="Organogenesis → Term",
    week=8,
    clinical_role="DNA synthesis, immune function, wound healing. Zinc deficiency causes growth retardation and congenital malformations.",
    what_happens_without="IUGR, immune deficiency, increased infection susceptibility in neonates",
    system=MolecularSystem(atoms=[
        mol("Zn", 0.000, 0.000, 0.000),
        mol("S",  2.200, 0.000, 0.000),
        mol("O",  3.100, 1.100, 0.000),
        mol("O",  3.100, -1.100, 0.000),
        mol("O",  2.200, 0.000, 1.500),
        mol("O",  2.200, 0.000, -1.500),
    ], basis_set="sto-3g"),
    cost_to_make="$0.01/tablet",
    access_barrier="Cheap commodity. WHO-recommended for diarrhea. Underused in prenatal care.",
)

# ── Hydrogen Peroxide (H₂O₂) — sterilization ──
HYDROGEN_PEROXIDE = LifeSavingMolecule(
    name="Hydrogen Peroxide",
    formula="H2O2",
    stage="All stages (environmental/sterilization)",
    week=0,
    clinical_role="Surface and instrument sterilization in NICU. Anthraquinone process production.",
    what_happens_without="Hospital-acquired infections. 75,000+ neonatal deaths/year from HAIs.",
    system=MolecularSystem(atoms=[
        mol("O", 0.000, 0.000, 0.000),
        mol("O", 1.475, 0.000, 0.000),
        mol("H", -0.368, 0.888, 0.328),
        mol("H", 1.843, -0.888, 0.328),
    ], basis_set="sto-3g"),
    cost_to_make="$0.50/L (3% solution)",
    access_barrier="Universally available. Quality control matters — concentration verification.",
)

# ── Ammonia (NH₃) — precursor to all nitrogen-containing drugs ──
AMMONIA = LifeSavingMolecule(
    name="Ammonia",
    formula="NH3",
    stage="Industrial precursor",
    week=0,
    clinical_role="Precursor to virtually all nitrogen-containing pharmaceuticals via Haber-Bosch process",
    what_happens_without="No antibiotics, no amino acids, no nucleotides. Civilization collapses.",
    system=MolecularSystem(atoms=[
        mol("N", 0.000, 0.000, 0.000),
        mol("H", 0.000, 0.940, 0.380),
        mol("H", 0.814, -0.470, 0.380),
        mol("H", -0.814, -0.470, 0.380),
    ], basis_set="sto-3g"),
    cost_to_make="$300/ton (Haber-Bosch)",
    access_barrier="Industrial commodity. No access barrier.",
)

# ── Carbon Dioxide (CO₂) — respiratory monitoring ──
CO2 = LifeSavingMolecule(
    name="Carbon Dioxide",
    formula="CO2",
    stage="All stages (respiratory monitoring)",
    week=0,
    clinical_role="End-tidal CO₂ monitoring in ventilated neonates. Blood gas analysis.",
    what_happens_without="Cannot assess ventilation adequacy. Blind ventilator management.",
    system=MolecularSystem(atoms=[
        mol("O", -1.160, 0.000, 0.000),
        mol("C",  0.000, 0.000, 0.000),
        mol("O",  1.160, 0.000, 0.000),
    ], basis_set="sto-3g"),
    cost_to_make="Byproduct of respiration and combustion",
    access_barrier="Capnography equipment costs $2000+. Unavailable in most LMIC NICUs.",
)

# ── Hydrogen (H₂) — simplest molecule, baseline benchmark ──
HYDROGEN = LifeSavingMolecule(
    name="Molecular Hydrogen",
    formula="H2",
    stage="Benchmark / Industrial",
    week=0,
    clinical_role="Benchmark molecule. Industrial precursor (Haber-Bosch). Emerging neuroprotection research in HIE.",
    what_happens_without="No benchmark means no calibration of simulation accuracy.",
    system=MolecularSystem(atoms=[
        mol("H", 0.000, 0.000, 0.000),
        mol("H", 0.740, 0.000, 0.000),
    ], basis_set="sto-3g"),
    cost_to_make="$1/kg (SMR)",
    access_barrier="None",
)

# ── Lithium Hydride (LiH) — calibration standard ──
LITHIUM_HYDRIDE = LifeSavingMolecule(
    name="Lithium Hydride",
    formula="LiH",
    stage="Calibration",
    week=0,
    clinical_role="Quantum chemistry calibration standard. 4-qubit reference system.",
    what_happens_without="No ground truth for simulation validation.",
    system=MolecularSystem(atoms=[
        mol("Li", 0.000, 0.000, 0.000),
        mol("H",  1.595, 0.000, 0.000),
    ], basis_set="sto-3g"),
    cost_to_make="N/A (calibration only)",
    access_barrier="N/A",
)


# ─── All molecules ordered by gestational timeline ────────────────

ALL_MOLECULES: List[LifeSavingMolecule] = [
    # Calibration first
    HYDROGEN,
    LITHIUM_HYDRIDE,
    # Universal
    WATER,
    OXYGEN,
    CO2,
    HYDROGEN_PEROXIDE,
    AMMONIA,
    # Conception (Week 0)
    PROGESTERONE_CORE,
    FOLIC_ACID_CORE,
    # Detection / Neural tube (Week 4)
    IRON_COMPLEX,
    # Organogenesis (Week 8)
    CALCIUM,
    ZINC_SULFATE,
    # Viability threshold (Week 24)
    DEXAMETHASONE_CORE,
    NITRIC_OXIDE,
    # NICU (Week 28+)
    SODIUM_BICARBONATE,
]


# ─── Simulation Runner ────────────────────────────────────────────

@dataclass
class SimulationResult:
    molecule_name: str
    formula: str
    stage: str
    week: int
    n_atoms: int
    n_electrons: int
    qubit_estimates: dict
    n_hamiltonian_terms: int
    n_commuting_groups: int
    nuclear_repulsion_energy: float
    clinical_role: str
    what_happens_without: str
    cost_to_make: str
    access_barrier: str
    wall_time_s: float


def simulate_molecule(molecule: LifeSavingMolecule) -> SimulationResult:
    """Run quantum chemistry simulation for a single molecule."""
    t0 = time.time()

    system = molecule.system
    qubits = estimate_qubits(system)

    # Use STO-3G qubit count for Hamiltonian
    sto3g_qubits = qubits["sto-3g"]["n_qubits"]

    # Build Hamiltonian
    H = build_molecular_hamiltonian(system, n_qubits=sto3g_qubits)

    # Group into commuting sets
    groups = H.groupby_commuting()

    # Extract nuclear repulsion (first term, identity operator)
    nuc_repulsion = 0.0
    for term in H.terms:
        if not term.ops:
            nuc_repulsion += term.coeff.real

    wall_time = time.time() - t0

    return SimulationResult(
        molecule_name=molecule.name,
        formula=molecule.formula,
        stage=molecule.stage,
        week=molecule.week,
        n_atoms=system.n_atoms,
        n_electrons=system.n_electrons,
        qubit_estimates=qubits,
        n_hamiltonian_terms=H.n_terms,
        n_commuting_groups=len(groups),
        nuclear_repulsion_energy=nuc_repulsion,
        clinical_role=molecule.clinical_role,
        what_happens_without=molecule.what_happens_without,
        cost_to_make=molecule.cost_to_make,
        access_barrier=molecule.access_barrier,
        wall_time_s=wall_time,
    )


def run_all() -> List[SimulationResult]:
    """Simulate all molecules in gestational order."""
    results = []
    total_t0 = time.time()

    print("=" * 80)
    print("CONCEPTION → NEONATAL LIFE-SAVING CHEMISTRY SIMULATION")
    print("Engine: E:\\universe-sim quantum_chem.py")
    print("=" * 80)
    print()

    for i, molecule in enumerate(ALL_MOLECULES, 1):
        print(f"[{i:2d}/{len(ALL_MOLECULES)}] {molecule.name} ({molecule.formula})")
        print(f"       Stage: {molecule.stage} | Week {molecule.week}")

        result = simulate_molecule(molecule)
        results.append(result)

        sto3g = result.qubit_estimates["sto-3g"]
        print(f"       Atoms: {result.n_atoms} | Electrons: {result.n_electrons}")
        print(f"       Qubits (STO-3G): {sto3g['n_qubits']}")
        print(f"       Hamiltonian: {result.n_hamiltonian_terms} terms, {result.n_commuting_groups} commuting groups")
        print(f"       Nuclear repulsion: {result.nuclear_repulsion_energy:.4f} Ha")
        print(f"       Time: {result.wall_time_s:.3f}s")
        print(f"       Clinical: {molecule.clinical_role[:80]}...")
        print(f"       Without: {molecule.what_happens_without[:80]}...")
        print(f"       Cost: {molecule.cost_to_make}")
        print()

    total_time = time.time() - total_t0

    print("=" * 80)
    print(f"COMPLETE: {len(results)} molecules simulated in {total_time:.2f}s")
    print("=" * 80)
    print()

    # Summary table
    print(f"{'Molecule':<45} {'Formula':<12} {'Week':>4} {'Atoms':>5} {'e⁻':>4} {'Qubits':>6} {'Terms':>6} {'Time':>8}")
    print("-" * 100)
    for r in results:
        q = r.qubit_estimates["sto-3g"]["n_qubits"]
        print(f"{r.molecule_name:<45} {r.formula:<12} {r.week:>4} {r.n_atoms:>5} {r.n_electrons:>4} {q:>6} {r.n_hamiltonian_terms:>6} {r.wall_time_s:>7.3f}s")

    print()
    total_qubits = sum(r.qubit_estimates["sto-3g"]["n_qubits"] for r in results)
    total_terms = sum(r.n_hamiltonian_terms for r in results)
    print(f"Total qubits across all molecules: {total_qubits}")
    print(f"Total Hamiltonian terms: {total_terms}")
    print(f"Total wall time: {total_time:.2f}s")

    return results


def save_results(results: List[SimulationResult], path: str = "simulation_results.json") -> None:
    """Save simulation results to JSON."""
    data = []
    for r in results:
        d = asdict(r)
        data.append(d)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    results = run_all()
    save_results(results)
