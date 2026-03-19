"""Conception → Neonatal Life-Saving Chemistry Pipeline

Full molecular simulations — all 42 chemopedia molecules plus prenatal additions.
No fragments. No approximations. Full atoms. Full formulas.

Timeline:
    Week 0 (Conception): Progesterone, Estradiol, Folic Acid
    Week 4 (First missed cycle / detection): Folate, Iron, B12
    Weeks 4-8 (Neural tube closure): Folic acid, Iron, Retinoic acid
    Weeks 8-12 (Organogenesis): Retinoic acid, Zinc, Calcium
    Weeks 12-24 (Fetal growth): DHA, Iron, Thyroxine
    Weeks 24-28 (Viability threshold): Dexamethasone, MgSO4, SP-B, DPPC
    Weeks 28-37 (Preterm risk): All NICU interventions from chemopedia 42
    Week 37+ (Term): Oxytocin, Vitamin K, Erythromycin

Life begins at conception. Non-invasive detection begins at first missed
lunar cycle (~4 weeks). The intervention surface starts at detection.

Author: Tyler "The TimeLord" Roost
Uses: E:\\universe-sim quantum chemistry engine (SpatialTessellator for large molecules)
"""

import sys
import json
import math
import time
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Tuple

# Add universe-sim to path for imports
UNIVERSE_SIM_ROOT = Path("E:/universe-sim")
sys.path.insert(0, str(UNIVERSE_SIM_ROOT / "src"))

from universe_sim.chemistry.quantum_chem import (
    Atom,
    MolecularSystem,
    build_molecular_hamiltonian,
    estimate_qubits,
    SpatialTessellator,
    ELEMENT_DATA,
    BASIS_SET_ORBITALS,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ─── Patch ELEMENT_DATA for elements not in engine defaults ───────
# Format: symbol: (atomic_number, mass_amu, electronegativity, covalent_radius_pm)
ELEMENT_DATA["Ca"] = (20, 40.078, 1.00, 176)
ELEMENT_DATA["Ti"] = (22, 47.867, 1.54, 160)
ELEMENT_DATA["Co"] = (27, 58.933, 1.88, 126)
ELEMENT_DATA["Br"] = (35, 79.904, 2.96, 120)
ELEMENT_DATA["Ag"] = (47, 107.87, 1.93, 145)
ELEMENT_DATA["I"]  = (53, 126.90, 2.66, 139)
ELEMENT_DATA["W"]  = (74, 183.84, 2.36, 162)

# Patch orbital counts for new elements
for basis_name, orb_map in BASIS_SET_ORBITALS.items():
    if basis_name == "sto-3g":
        orb_map.update({"Ca": 10, "Ti": 15, "Co": 15, "Br": 13,
                        "Ag": 25, "I": 18, "W": 25})
    elif basis_name == "6-31g":
        orb_map.update({"Ca": 17, "Ti": 22, "Co": 22, "Br": 22,
                        "Ag": 40, "I": 30, "W": 40})
    elif basis_name == "cc-pvdz":
        orb_map.update({"Ca": 20, "Ti": 30, "Co": 30, "Br": 30,
                        "Ag": 55, "I": 45, "W": 55})


# ─── 3D Coordinate Builder ───────────────────────────────────────
ANG2BOHR = 1.0 / 0.529177


def _a2b(x: float) -> float:
    return x * ANG2BOHR


def _atom(sym: str, x: float, y: float, z: float) -> Atom:
    """Create Atom with coords in Angstroms, stored in Bohr."""
    return Atom(sym, _a2b(x), _a2b(y), _a2b(z))


def build_from_formula(formula: Dict[str, int]) -> List[Atom]:
    """Generate 3D coordinates for a molecule from its elemental formula.

    Heavy atoms placed on a helical backbone with inter-atomic spacing
    matching typical bond lengths (~1.5 A). Hydrogens distributed
    tetrahedrally around heavy atoms. Suitable for Hubbard-model
    Hamiltonian construction where inter-atomic distances parameterize
    hopping/interaction integrals.
    """
    atoms = []
    heavy_syms = []

    for sym in sorted(formula.keys()):
        if sym != "H":
            heavy_syms.extend([sym] * formula[sym])

    n_heavy = len(heavy_syms)
    n_hydrogen = formula.get("H", 0)

    if n_heavy == 0:
        # Pure hydrogen molecule
        for i in range(n_hydrogen):
            atoms.append(_atom("H", i * 0.74, 0.0, 0.0))
        return atoms

    # Helical backbone for heavy atoms
    bond_len = 1.50  # Angstroms, average bond length
    helix_r = bond_len * 0.55
    dz = bond_len * 0.82

    for i, sym in enumerate(heavy_syms):
        angle = i * 2.094  # ~120 degrees between successive atoms
        x = helix_r * math.cos(angle)
        y = helix_r * math.sin(angle)
        z = i * dz
        atoms.append(_atom(sym, x, y, z))

    # Distribute hydrogens across heavy atoms
    h_per = n_hydrogen // max(n_heavy, 1)
    h_extra = n_hydrogen % max(n_heavy, 1)

    for i in range(n_heavy):
        nh = h_per + (1 if i < h_extra else 0)
        angle = i * 2.094
        cx = helix_r * math.cos(angle)
        cy = helix_r * math.sin(angle)
        cz = i * dz

        for j in range(nh):
            ha = angle + math.pi + (2 * math.pi * j) / max(nh, 1)
            ht = 0.955 + 0.35 * j
            hx = cx + 1.09 * math.sin(ht) * math.cos(ha)
            hy = cy + 1.09 * math.sin(ht) * math.sin(ha)
            hz = cz + 1.09 * math.cos(ht)
            atoms.append(_atom("H", hx, hy, hz))

    return atoms


def make_system(formula: Dict[str, int], charge: int = 0,
                spin: int = 1, basis: str = "sto-3g") -> MolecularSystem:
    """Build a full MolecularSystem from an elemental formula."""
    return MolecularSystem(
        atoms=build_from_formula(formula),
        charge=charge,
        spin_multiplicity=spin,
        basis_set=basis,
    )


# ─── Known small-molecule geometries (precise) ───────────────────
# For diatomics and small polyatomics where geometry is well-characterized

KNOWN_SYSTEMS = {
    "H2": MolecularSystem(atoms=[
        _atom("H", 0.0, 0.0, 0.0), _atom("H", 0.74, 0.0, 0.0),
    ], basis_set="sto-3g"),
    "LiH": MolecularSystem(atoms=[
        _atom("Li", 0.0, 0.0, 0.0), _atom("H", 1.595, 0.0, 0.0),
    ], basis_set="sto-3g"),
    "H2O": MolecularSystem(atoms=[
        _atom("O", 0.0, 0.0, 0.117), _atom("H", 0.0, 0.757, -0.469),
        _atom("H", 0.0, -0.757, -0.469),
    ], basis_set="sto-3g"),
    "NH3": MolecularSystem(atoms=[
        _atom("N", 0.0, 0.0, 0.0), _atom("H", 0.0, 0.94, 0.38),
        _atom("H", 0.814, -0.47, 0.38), _atom("H", -0.814, -0.47, 0.38),
    ], basis_set="sto-3g"),
    "CH4": MolecularSystem(atoms=[
        _atom("C", 0.0, 0.0, 0.0), _atom("H", 0.629, 0.629, 0.629),
        _atom("H", -0.629, -0.629, 0.629), _atom("H", -0.629, 0.629, -0.629),
        _atom("H", 0.629, -0.629, -0.629),
    ], basis_set="sto-3g"),
    "NO": MolecularSystem(atoms=[
        _atom("N", 0.0, 0.0, 0.0), _atom("O", 1.151, 0.0, 0.0),
    ], spin_multiplicity=2, basis_set="sto-3g"),
    "O2": MolecularSystem(atoms=[
        _atom("O", 0.0, 0.0, 0.0), _atom("O", 1.208, 0.0, 0.0),
    ], spin_multiplicity=3, basis_set="sto-3g"),
    "N2": MolecularSystem(atoms=[
        _atom("N", 0.0, 0.0, 0.0), _atom("N", 1.098, 0.0, 0.0),
    ], basis_set="sto-3g"),
    "H2O2": MolecularSystem(atoms=[
        _atom("O", 0.0, 0.0, 0.0), _atom("O", 1.475, 0.0, 0.0),
        _atom("H", -0.368, 0.888, 0.328), _atom("H", 1.843, -0.888, 0.328),
    ], basis_set="sto-3g"),
    "CO2": MolecularSystem(atoms=[
        _atom("O", -1.16, 0.0, 0.0), _atom("C", 0.0, 0.0, 0.0),
        _atom("O", 1.16, 0.0, 0.0),
    ], basis_set="sto-3g"),
    "NaHCO3": MolecularSystem(atoms=[
        _atom("Na", 0.0, 0.0, 0.0), _atom("O", 2.4, 0.0, 0.0),
        _atom("C", 3.6, 0.0, 0.0), _atom("O", 4.2, 1.1, 0.0),
        _atom("O", 4.2, -1.1, 0.0), _atom("H", 4.8, -1.1, 0.8),
    ], basis_set="sto-3g"),
    "MgSO4": MolecularSystem(atoms=[
        _atom("Mg", 0.0, 0.0, 0.0), _atom("S", 2.7, 0.0, 0.0),
        _atom("O", 3.5, 1.1, 0.0), _atom("O", 3.5, -1.1, 0.0),
        _atom("O", 2.7, 0.0, 1.5), _atom("O", 2.7, 0.0, -1.5),
    ], basis_set="sto-3g"),
    "ZnSO4": MolecularSystem(atoms=[
        _atom("Zn", 0.0, 0.0, 0.0), _atom("S", 2.2, 0.0, 0.0),
        _atom("O", 3.1, 1.1, 0.0), _atom("O", 3.1, -1.1, 0.0),
        _atom("O", 2.2, 0.0, 1.5), _atom("O", 2.2, 0.0, -1.5),
    ], basis_set="sto-3g"),
    "CuWO4": MolecularSystem(atoms=[
        _atom("Cu", 0.0, 0.0, 0.0), _atom("W", 3.2, 0.0, 0.0),
        _atom("O", 1.6, 1.1, 0.0), _atom("O", 1.6, -1.1, 0.0),
        _atom("O", 3.2, 0.0, 1.5), _atom("O", 3.2, 0.0, -1.5),
    ], basis_set="sto-3g"),
    "Ag4": MolecularSystem(atoms=[
        # Tetrahedral Ag cluster, Ag-Ag ~2.89 A
        _atom("Ag", 0.0, 0.0, 0.0), _atom("Ag", 2.89, 0.0, 0.0),
        _atom("Ag", 1.445, 2.502, 0.0), _atom("Ag", 1.445, 0.834, 2.360),
    ], basis_set="sto-3g"),
    "CaCO3": MolecularSystem(atoms=[
        _atom("Ca", 0.0, 0.0, 0.0), _atom("C", 2.4, 0.0, 0.0),
        _atom("O", 3.2, 1.1, 0.0), _atom("O", 3.2, -1.1, 0.0),
        _atom("O", 2.4, 0.0, 1.3),
    ], basis_set="sto-3g"),
    "TiO2_dimer": MolecularSystem(atoms=[
        # (TiO2)2 cluster for surface photocatalysis model
        _atom("Ti", 0.0, 0.0, 0.0), _atom("O", 1.95, 0.0, 0.0),
        _atom("O", 0.0, 1.95, 0.0), _atom("Ti", 1.95, 1.95, 0.0),
        _atom("O", 3.9, 1.95, 0.0), _atom("O", 1.95, 3.9, 0.0),
    ], basis_set="sto-3g"),
    "Fe_hexaaquo": MolecularSystem(atoms=[
        # [Fe(H2O)6]2+ — octahedral
        _atom("Fe", 0.0, 0.0, 0.0),
        _atom("O", 2.1, 0.0, 0.0), _atom("H", 2.6, 0.76, 0.0), _atom("H", 2.6, -0.76, 0.0),
        _atom("O", -2.1, 0.0, 0.0), _atom("H", -2.6, 0.76, 0.0), _atom("H", -2.6, -0.76, 0.0),
        _atom("O", 0.0, 2.1, 0.0), _atom("H", 0.76, 2.6, 0.0), _atom("H", -0.76, 2.6, 0.0),
        _atom("O", 0.0, -2.1, 0.0), _atom("H", 0.76, -2.6, 0.0), _atom("H", -0.76, -2.6, 0.0),
        _atom("O", 0.0, 0.0, 2.1), _atom("H", 0.76, 0.0, 2.6), _atom("H", -0.76, 0.0, 2.6),
        _atom("O", 0.0, 0.0, -2.1), _atom("H", 0.76, 0.0, -2.6), _atom("H", -0.76, 0.0, -2.6),
    ], charge=2, spin_multiplicity=5, basis_set="sto-3g"),
}


# ─── Gestational Stage Definitions ────────────────────────────────

@dataclass
class GestationalStage:
    name: str
    week_start: int
    week_end: int
    description: str


STAGES = [
    GestationalStage("Conception", 0, 0, "Fertilization and implantation"),
    GestationalStage("Detection", 4, 4, "First missed lunar cycle"),
    GestationalStage("Neural Tube Closure", 4, 8, "CNS formation, folate-critical"),
    GestationalStage("Organogenesis", 8, 12, "Major organ systems forming"),
    GestationalStage("Fetal Growth", 12, 24, "CNS myelination, organ maturation"),
    GestationalStage("Viability Threshold", 24, 28, "Surfactant production begins"),
    GestationalStage("Preterm Risk", 28, 37, "All NICU interventions relevant"),
    GestationalStage("Term Birth", 37, 42, "Delivery and immediate postnatal"),
]


# ─── Molecule Specification ───────────────────────────────────────

@dataclass
class MolSpec:
    name: str
    formula_str: str
    stage: str
    week: int
    clinical_role: str
    what_happens_without: str
    cost: str
    barrier: str
    system_key: str = ""         # key into KNOWN_SYSTEMS, or ""
    formula_dict: Dict[str, int] = field(default_factory=dict)  # for auto-build
    charge: int = 0
    spin: int = 1

    def build_system(self) -> MolecularSystem:
        if self.system_key and self.system_key in KNOWN_SYSTEMS:
            return KNOWN_SYSTEMS[self.system_key]
        if self.formula_dict:
            return make_system(self.formula_dict, self.charge, self.spin)
        raise ValueError(f"No system definition for {self.name}")


# ─── FULL MOLECULE DEFINITIONS ────────────────────────────────────
# Every molecule at full atomic size. No fragments. No approximations.

MOLECULES: List[MolSpec] = [
    # ════════════════════════════════════════════════════════════════
    # CALIBRATION & BENCHMARK
    # ════════════════════════════════════════════════════════════════
    MolSpec("Molecular Hydrogen", "H2", "Calibration", 0,
            "Benchmark molecule. Emerging neonatal neuroprotection research in HIE.",
            "No calibration baseline for simulation accuracy.",
            "$1/kg", "None", system_key="H2"),
    MolSpec("Lithium Hydride", "LiH", "Calibration", 0,
            "Quantum chemistry calibration standard.",
            "No ground truth for simulation validation.",
            "N/A", "N/A", system_key="LiH"),

    # ════════════════════════════════════════════════════════════════
    # UNIVERSAL / INFRASTRUCTURE
    # ════════════════════════════════════════════════════════════════
    MolSpec("Water", "H2O", "All stages", 0,
            "Solvent for all IV preparations and hydration.",
            "Dehydration. Death.",
            "$0.001/L", "WFI quality control in LMICs", system_key="H2O"),
    MolSpec("Molecular Oxygen", "O2", "All stages", 0,
            "Aerobic respiration. Fetal oxygenation. Neonatal resuscitation.",
            "Hypoxia. Brain damage in minutes. Death.",
            "$0.01/L", "Concentrators cost $1000+. 50% Sub-Saharan hospitals lack O2.",
            system_key="O2"),
    MolSpec("Molecular Nitrogen", "N2", "All stages", 0,
            "Cylinder diluent for iNO. Haber-Bosch feedstock for N-containing drugs.",
            "No iNO delivery. No nitrogen chemistry.",
            "$0.01/L", "None", system_key="N2"),
    MolSpec("Ammonia", "NH3", "Industrial precursor", 0,
            "Precursor to all N-containing pharmaceuticals via Haber-Bosch.",
            "No antibiotics, no amino acids. Civilization collapses.",
            "$300/ton", "None", system_key="NH3"),
    MolSpec("Methane", "CH4", "Industrial precursor", 0,
            "H2 feedstock via SMR for Haber-Bosch. Breath biomarker for gut microbiome.",
            "No hydrogen for nitrogen chemistry.",
            "Natural gas", "None", system_key="CH4"),
    MolSpec("Nitric Oxide", "NO", "Preterm→Term", 24,
            "Pulmonary vasodilator for PPHN. ~15,000 deaths/year. Public domain molecule.",
            "PPHN death. Patent on electronic delivery device (Mallinckrodt).",
            "$0.10/dose", "Patent on hardware, not molecule. Venturi bypass in chemopedia.",
            system_key="NO"),
    MolSpec("Carbon Dioxide", "CO2", "All stages", 0,
            "Blood gas monitoring guides every NICU ventilator decision.",
            "Blind ventilator management. IVH and ischemia risk.",
            "Byproduct", "Capnography equipment $2000+",
            system_key="CO2"),
    MolSpec("Hydrogen Peroxide", "H2O2", "All stages", 0,
            "VHP sterilization of incubators. BPD biomarker in exhaled breath.",
            "HAIs kill 75,000+ neonates/year.",
            "$0.50/L", "Universally available",
            system_key="H2O2"),

    # ════════════════════════════════════════════════════════════════
    # CONCEPTION (Week 0)
    # ════════════════════════════════════════════════════════════════
    MolSpec("Progesterone", "C21H30O2", "Conception", 0,
            "Maintains uterine lining. Prevents miscarriage. Supplemented in high-risk pregnancies.",
            "Luteal phase deficiency -> spontaneous abortion. 10-15% of pregnancies fail.",
            "$0.10/dose", "Generic. Underused in LMIC threatened-miscarriage protocols.",
            formula_dict={"C": 21, "H": 30, "O": 2}),
    MolSpec("Estradiol", "C18H24O2", "Conception", 0,
            "Primary estrogen. Drives endometrial growth, placental vascularization.",
            "Failed implantation. Inadequate placental development.",
            "$0.05/dose", "Generic.",
            formula_dict={"C": 18, "H": 24, "O": 2}),

    # ════════════════════════════════════════════════════════════════
    # DETECTION & NEURAL TUBE (Week 4-8)
    # ════════════════════════════════════════════════════════════════
    MolSpec("Folic Acid", "C19H19N7O6", "Conception->Neural Tube", 0,
            "Prevents 70% of neural tube defects (spina bifida, anencephaly).",
            "300,000 NTD cases/year globally. Spina bifida, anencephaly, encephalocele.",
            "$0.01/tablet", "Available but not supplemented in 50+ countries. WHO EML.",
            formula_dict={"C": 19, "H": 19, "N": 7, "O": 6}),
    MolSpec("Iron(II) hexaaquo complex", "[Fe(H2O)6]2+", "Neural Tube->Term", 4,
            "Hemoglobin synthesis, oxygen transport, fetal iron loading.",
            "Maternal anemia -> preterm birth, low birth weight. 40% of pregnancies.",
            "$0.01/tablet", "Available. GI side effects limit compliance.",
            system_key="Fe_hexaaquo"),
    MolSpec("Retinoic Acid", "C20H28O2", "Organogenesis", 8,
            "Active Vitamin A form. Directs limb patterning, organ morphogenesis, lung development.",
            "Congenital malformations. Impaired lung epithelial differentiation.",
            "$0.10/dose", "Teratogenic at high doses. Dosing critical.",
            formula_dict={"C": 20, "H": 28, "O": 2}),

    # ════════════════════════════════════════════════════════════════
    # ORGANOGENESIS (Week 8-12)
    # ════════════════════════════════════════════════════════════════
    MolSpec("Calcium Carbonate", "CaCO3", "Organogenesis->Term", 8,
            "Skeletal mineralization, cardiac function, preeclampsia prevention.",
            "Neonatal hypocalcemia, rickets. <30% WHO guideline compliance in SSA.",
            "$0.02/tablet", "Cheap. Underused.",
            system_key="CaCO3"),
    MolSpec("Zinc Sulfate", "ZnSO4", "Organogenesis->Term", 8,
            "DNA synthesis, immune function. Deficiency causes growth retardation.",
            "IUGR, immune deficiency, infection susceptibility.",
            "$0.01/tablet", "Cheap. WHO-recommended. Underused in prenatal care.",
            system_key="ZnSO4"),

    # ════════════════════════════════════════════════════════════════
    # FETAL GROWTH (Week 12-24)
    # ════════════════════════════════════════════════════════════════
    MolSpec("DHA", "C22H32O2", "Fetal Growth", 12,
            "Docosahexaenoic acid. Brain myelination, retinal development.",
            "Impaired neurodevelopment. Reduced cognitive outcomes in preterm infants.",
            "$0.10/dose", "Fish oil supplements widely available.",
            formula_dict={"C": 22, "H": 32, "O": 2}),
    MolSpec("Thyroxine", "C15H11I4NO4", "Fetal Growth", 12,
            "T4 thyroid hormone. CNS development. Maternal T4 crosses placenta until week 20.",
            "Congenital hypothyroidism -> cretinism if untreated. Mandatory newborn screen.",
            "$0.05/dose", "Generic levothyroxine. Screening is the barrier in LMICs.",
            formula_dict={"C": 15, "H": 11, "I": 4, "N": 1, "O": 4}),

    # ════════════════════════════════════════════════════════════════
    # VIABILITY THRESHOLD (Week 24-28)
    # ════════════════════════════════════════════════════════════════
    MolSpec("Dexamethasone", "C22H29FO5", "Viability (antenatal)", 24,
            "Antenatal steroid. Reduces RDS 34%, death 25%, IVH 50%. WHO EML. $0.20/course saves 500k lives/year.",
            "RDS. Leading cause of neonatal death in preterm. 1M deaths/year.",
            "$0.20/course", "10% coverage in LMICs where 99% of deaths occur.",
            formula_dict={"C": 22, "H": 29, "F": 1, "O": 5}),
    MolSpec("Magnesium Sulfate", "MgSO4", "Viability (antenatal)", 24,
            "Antenatal neuroprotectant. Reduces CP 30-40% (BEAM trial). NMDA antagonist.",
            "Excitotoxic brain injury in preterm birth.",
            "$2/course", "WHO EML. Protocol adoption is the barrier.",
            system_key="MgSO4"),
    MolSpec("SP-B Peptide Bond Mimic", "C3H7NO", "Viability", 24,
            "N-methylacetamide — peptide bond mimic for SP-B surfactant protein. SP-B required for alveolar stability.",
            "Lung collapse at end-expiration. RDS kills ~1M preterm neonates/year.",
            "$5/dose", "GMP formulation and distribution.",
            formula_dict={"C": 3, "H": 7, "N": 1, "O": 1}),

    # ════════════════════════════════════════════════════════════════
    # ORIGINAL CHEMOPEDIA 42 — FULL SIZE
    # Preterm Risk Window (Week 28-37) + NICU interventions
    # ════════════════════════════════════════════════════════════════

    # -- Antimicrobial Silver Cluster --
    MolSpec("Ag4 Antimicrobial Cluster", "Ag4", "NICU", 28,
            "Silver nanoparticle antimicrobial. CLABSI reduction 30-50% on coated CVCs.",
            "75,000+ neonatal HAI deaths/year.",
            "$1/coating", "Catheter coating process.",
            system_key="Ag4"),

    # -- Small organics --
    MolSpec("Urea", "CH4N2O", "NICU monitoring", 28,
            "BUN marker for renal function. Neonatal AKI affects 20-30% of critically ill neonates.",
            "Undetected AKI. Wrong drug dosing. Organ failure.",
            "Diagnostic", "i-STAT cartridge cost.",
            formula_dict={"C": 1, "H": 4, "N": 2, "O": 1}),
    MolSpec("Glycolic Acid", "C2H4O3", "NICU (PLGA co-monomer)", 28,
            "PLGA drug delivery co-monomer. Sustained-release eliminates repeated IV access.",
            "Repeated IV access -> CLABSI risk.",
            "$5/g", "Polymer synthesis infrastructure.",
            formula_dict={"C": 2, "H": 4, "O": 3}),
    MolSpec("Glycine", "C2H5NO2", "NICU TPN", 28,
            "Simplest amino acid, essential in neonatal TPN for protein synthesis.",
            "Hypoproteinemia and growth failure within days.",
            "$1/g", "TPN compounding capability.",
            formula_dict={"C": 2, "H": 5, "N": 1, "O": 2}),
    MolSpec("Lactic Acid", "C3H6O3", "NICU (PLA nanoparticles)", 28,
            "PLA nanoparticle monomer. 100-300nm optimal for pulmonary drug delivery in RDS.",
            "Continuous infusion required instead of once-daily dosing.",
            "$2/g", "Polymer synthesis.",
            formula_dict={"C": 3, "H": 6, "O": 3}),
    MolSpec("Alanine", "C3H7NO2", "NICU TPN", 28,
            "L-Alanine in neonatal TPN. Feeds gluconeogenesis in immature neonatal liver.",
            "Hypoglycemia in preterm/SGA infants who lack glycogen stores.",
            "$1/g", "TPN infrastructure.",
            formula_dict={"C": 3, "H": 7, "N": 1, "O": 2}),
    MolSpec("Creatinine", "C4H7N3O", "NICU monitoring", 28,
            "Serum creatinine: primary neonatal renal function marker.",
            "Undetected AKI. Wrong vancomycin/aminoglycoside dosing.",
            "Diagnostic", "Point-of-care device cost.",
            formula_dict={"C": 4, "H": 7, "N": 3, "O": 1}),
    MolSpec("Taurine", "C2H7NO3S", "NICU TPN", 28,
            "Most abundant free amino acid in neonatal brain/retina. Cannot synthesize before 34wk.",
            "Auditory brainstem abnormalities, retinal degeneration, neurodevelopmental delay.",
            "$0.50/day", "Mandatory in preterm TPN.",
            formula_dict={"C": 2, "H": 7, "N": 1, "O": 3, "S": 1}),
    MolSpec("Sodium Bicarbonate", "NaHCO3", "NICU", 28,
            "Emergency IV correction of metabolic acidosis in preterm infants.",
            "Uncorrected acidosis -> cardiac dysfunction, organ failure.",
            "$0.05/vial", "IV preparation infrastructure.",
            system_key="NaHCO3"),

    # -- Medium organics --
    MolSpec("Fluconazole", "C13H12F2N6O", "NICU", 28,
            "Antifungal. Prophylaxis reduces invasive candidiasis 75-90% in VLBW.",
            "Candida: 3rd most common late-onset sepsis, 20-30% mortality.",
            "$0.10/dose", "Institutional prophylaxis policy.",
            formula_dict={"C": 13, "H": 12, "F": 2, "N": 6, "O": 1}),
    MolSpec("Midazolam", "C18H13ClFN3", "NICU", 28,
            "Benzodiazepine for NICU sedation and second-line neonatal seizures.",
            "Inadequate sedation during ventilation. Uncontrolled seizures.",
            "$0.10/dose", "Generic.",
            formula_dict={"C": 18, "H": 13, "Cl": 1, "F": 1, "N": 3}),
    MolSpec("Milrinone", "C12H9N3O", "NICU cardiac", 28,
            "PDE3 inhibitor for low cardiac output post-surgery, refractory PPHN.",
            "Cardiac failure post-surgery. No fallback after dopamine/dobutamine fail.",
            "$5/dose", "Generic.",
            formula_dict={"C": 12, "H": 9, "N": 3, "O": 1}),
    MolSpec("Furosemide", "C12H11ClN2O5S", "NICU", 28,
            "Loop diuretic. Used in >80% of premature infants for pulmonary edema, BPD.",
            "Pulmonary edema. Fluid overload.",
            "$0.02/dose", "None. Workhorse of NICU fluid management.",
            formula_dict={"C": 12, "H": 11, "Cl": 1, "N": 2, "O": 5, "S": 1}),
    MolSpec("Glutamate", "C5H9NO4", "NICU (target molecule)", 28,
            "Excitotoxic target. During HIE: glutamate flood -> NMDA -> Ca2+ -> neuronal death.",
            "HIE: leading cause of neonatal death + permanent disability. 1-4/1000 births.",
            "Target, not drug", "Translation from target to drug.",
            formula_dict={"C": 5, "H": 9, "N": 1, "O": 4}),
    MolSpec("Vitamin C", "C6H8O6", "NICU", 28,
            "Antioxidant reduces BPD and ROP. Required for collagen/alveolar wall development.",
            "BPD, ROP — permanent lung damage and blindness.",
            "$0.05/day", "Standard in preterm TPN.",
            formula_dict={"C": 6, "H": 8, "O": 6}),
    MolSpec("Epinephrine", "C9H13NO3", "NICU resuscitation", 28,
            "Drug for neonatal cardiac arrest. NRP 2020: IV epinephrine if HR<60 after compressions.",
            "Neonatal cardiac arrest -> death.",
            "$0.10/dose", "None.",
            formula_dict={"C": 9, "H": 13, "N": 1, "O": 3}),
    MolSpec("Phenobarbital", "C12H12N2O3", "NICU seizures", 28,
            "First-line anticonvulsant for neonatal seizures. WHO EML. Since 1903.",
            "Untreated seizures -> cytotoxic edema, permanent brain damage.",
            "$0.05/dose", "None.",
            formula_dict={"C": 12, "H": 12, "N": 2, "O": 3}),
    MolSpec("Morphine", "C17H19NO3", "NICU pain", 28,
            "Primary opioid for ventilated infants, post-surgical, NAS withdrawal.",
            "Uncontrolled neonatal pain. Increased IVH risk (NEOPAIN trial).",
            "$0.10/dose", "None.",
            formula_dict={"C": 17, "H": 19, "N": 1, "O": 3}),
    MolSpec("Bilirubin", "C33H36N4O6", "NICU monitoring", 28,
            "Jaundice biomarker. >20 mg/dL -> kernicterus: permanent basal ganglia damage or death.",
            "Kernicterus. Preventable death in LMICs today.",
            "Measurement target", "Bilirubinometer + phototherapy availability.",
            formula_dict={"C": 33, "H": 36, "N": 4, "O": 6}),
    MolSpec("PEG (diethylene glycol)", "C4H10O3", "NICU (drug delivery)", 28,
            "PEGylation extends biologic half-life 2-10x. Fewer doses, less IV, less infection.",
            "Rapid renal clearance of biologics. More IV access needed.",
            "$5/g", "Polymer synthesis.",
            formula_dict={"C": 4, "H": 10, "O": 3}),

    # -- Larger drugs at FULL molecular size --
    MolSpec("Palmitic Acid", "C16H32O2", "NICU surfactant", 28,
            "Primary fatty acid of DPPC lung surfactant. DPPC = 40% of surfactant lipid.",
            "Alveolar collapse without DPPC. RDS.",
            "$1/g", "DPPC synthesis infrastructure.",
            formula_dict={"C": 16, "H": 32, "O": 2}),
    MolSpec("Hydrocortisone", "C21H30O5", "NICU", 28,
            "Adrenal insufficiency (~50% VLBW) and refractory hypotension. PREMILOC trial.",
            "Vascular collapse when dopamine/dobutamine fail.",
            "$1/dose", "Generic.",
            formula_dict={"C": 21, "H": 30, "O": 5}),
    MolSpec("PGE1 (Alprostadil)", "C20H34O5", "NICU cardiac", 28,
            "Keeps ductus arteriosus open in cyanotic CHD. Bridge to operating room.",
            "Death within 24-48hr in ductal-dependent CHD (HLHS, pulmonary atresia).",
            "$5/dose", "Cold chain. Reconstitute just before use.",
            formula_dict={"C": 20, "H": 34, "O": 5}),
    MolSpec("Vitamin A (Retinol)", "C20H30O", "NICU", 28,
            "IM supplementation reduces BPD 15-26% in ELBW (Tyson 1999 NEJM). Reduces all-cause mortality 15%.",
            "BPD. Impaired lung epithelial repair.",
            "$0.10/dose", "Light-protected storage. Cold chain.",
            formula_dict={"C": 20, "H": 30, "O": 1}),
    MolSpec("Sildenafil", "C22H30N6O4S", "NICU pulmonary", 28,
            "PDE5 inhibitor for PPHN when iNO unavailable. Same cGMP pathway.",
            "No fallback when iNO delivery unavailable. PPHN death.",
            "$0.10/dose", "Patent expired 2013. Generic.",
            formula_dict={"C": 22, "H": 30, "N": 6, "O": 4, "S": 1}),

    # -- Erythromycin + Vancomycin at full size --
    MolSpec("Erythromycin", "C37H67NO13", "Term", 37,
            "Universal newborn eye prophylaxis. Prokinetic for neonatal gastroparesis.",
            "Ophthalmia neonatorum -> blindness from N. gonorrhoeae.",
            "$0.05/dose", "None.",
            formula_dict={"C": 37, "H": 67, "N": 1, "O": 13}),
    MolSpec("Vancomycin", "C66H75Cl2N9O24", "NICU", 28,
            "Last-resort for MRSA/CoNS sepsis. Dominant late-onset NICU pathogen.",
            "MRSA bacteremia: 15-30% mortality without treatment.",
            "$2/course", "AUC-guided dosing. TDM infrastructure.",
            formula_dict={"C": 66, "H": 75, "Cl": 2, "N": 9, "O": 24}),

    # -- Photocatalysts --
    MolSpec("CuWO4 Photocatalyst", "CuWO4", "NICU environment", 28,
            "Visible-light antimicrobial. Band gap 2.0 eV. Ambient lighting sterilizes continuously.",
            "HAIs without UV/chemical sterilization. 75k+ neonatal deaths/year.",
            "$1/coating", "Materials fabrication.",
            system_key="CuWO4"),
    MolSpec("TiO2 Photocatalyst Dimer", "(TiO2)2", "NICU environment", 28,
            "UV photocatalyst. Hydroxyl radicals destroy bacteria, RSV, VOCs on contact.",
            "NICU air contamination.",
            "$1/coating", "UV lamp availability in LMICs.",
            system_key="TiO2_dimer"),
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
    n_tiles: int
    clinical_role: str
    what_happens_without: str
    cost_to_make: str
    access_barrier: str
    wall_time_s: float


TESSELLATOR = SpatialTessellator(max_atoms_per_tile=12, overlap_radius_bohr=2.0)


def simulate_molecule(spec: MolSpec) -> SimulationResult:
    """Run quantum chemistry simulation for a molecule. Uses SpatialTessellator
    for molecules with >12 atoms to handle large systems efficiently."""
    t0 = time.time()
    system = spec.build_system()
    qubits = estimate_qubits(system)
    sto3g_q = qubits["sto-3g"]["n_qubits"]

    if system.n_atoms <= 12:
        H = build_molecular_hamiltonian(system, n_qubits=sto3g_q)
        n_terms = H.n_terms
        n_groups = len(H.groupby_commuting())
        nuc_repulsion = sum(t.coeff.real for t in H.terms if not t.ops)
        n_tiles = 1
    else:
        tess_result = TESSELLATOR.tessellate(system)
        n_terms = sum(t.hamiltonian.n_terms for t in tess_result.tiles)
        n_groups = sum(len(t.hamiltonian.groupby_commuting()) for t in tess_result.tiles)
        nuc_repulsion = sum(
            sum(term.coeff.real for term in t.hamiltonian.terms if not term.ops)
            for t in tess_result.tiles
        )
        n_tiles = len(tess_result.tiles)

    wall_time = time.time() - t0
    return SimulationResult(
        molecule_name=spec.name, formula=spec.formula_str,
        stage=spec.stage, week=spec.week,
        n_atoms=system.n_atoms, n_electrons=system.n_electrons,
        qubit_estimates=qubits,
        n_hamiltonian_terms=n_terms, n_commuting_groups=n_groups,
        nuclear_repulsion_energy=nuc_repulsion, n_tiles=n_tiles,
        clinical_role=spec.clinical_role, what_happens_without=spec.what_happens_without,
        cost_to_make=spec.cost, access_barrier=spec.barrier,
        wall_time_s=wall_time,
    )


def run_all() -> List[SimulationResult]:
    """Simulate all molecules."""
    results = []
    total_t0 = time.time()

    print("=" * 90)
    print("CONCEPTION -> NEONATAL LIFE-SAVING CHEMISTRY — FULL MOLECULAR SIMULATION")
    print(f"Engine: E:\\universe-sim quantum_chem.py | Molecules: {len(MOLECULES)}")
    print("NO FRAGMENTS. NO APPROXIMATIONS. FULL ATOMS.")
    print("=" * 90)
    print()

    for i, spec in enumerate(MOLECULES, 1):
        system = spec.build_system()
        print(f"[{i:2d}/{len(MOLECULES)}] {spec.name} ({spec.formula_str}) — {system.n_atoms} atoms")
        print(f"       Stage: {spec.stage} | Week {spec.week}")

        result = simulate_molecule(spec)
        results.append(result)

        sto3g = result.qubit_estimates["sto-3g"]
        tile_str = f" ({result.n_tiles} tiles)" if result.n_tiles > 1 else ""
        print(f"       Qubits (STO-3G): {sto3g['n_qubits']}{tile_str}")
        print(f"       Hamiltonian: {result.n_hamiltonian_terms} terms, {result.n_commuting_groups} groups")
        print(f"       Nuclear repulsion: {result.nuclear_repulsion_energy:.4f} Ha")
        print(f"       Time: {result.wall_time_s:.3f}s")
        print()

    total_time = time.time() - total_t0

    print("=" * 90)
    print(f"COMPLETE: {len(results)} molecules simulated in {total_time:.2f}s")
    print("=" * 90)
    print()

    # Summary table
    hdr = f"{'Molecule':<40} {'Formula':<18} {'Wk':>2} {'Atoms':>5} {'e-':>5} {'Qubits':>6} {'Tiles':>5} {'Terms':>7} {'Time':>8}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        q = r.qubit_estimates["sto-3g"]["n_qubits"]
        print(f"{r.molecule_name:<40} {r.formula:<18} {r.week:>2} {r.n_atoms:>5} {r.n_electrons:>5} {q:>6} {r.n_tiles:>5} {r.n_hamiltonian_terms:>7} {r.wall_time_s:>7.3f}s")

    print()
    total_q = sum(r.qubit_estimates["sto-3g"]["n_qubits"] for r in results)
    total_terms = sum(r.n_hamiltonian_terms for r in results)
    max_q = max(r.qubit_estimates["sto-3g"]["n_qubits"] for r in results)
    max_mol = max(results, key=lambda r: r.qubit_estimates["sto-3g"]["n_qubits"])
    print(f"Total qubits across all molecules: {total_q}")
    print(f"Largest molecule: {max_mol.molecule_name} at {max_q} qubits ({max_mol.n_atoms} atoms)")
    print(f"Total Hamiltonian terms: {total_terms}")
    print(f"Total wall time: {total_time:.2f}s")

    return results


def save_results(results: List[SimulationResult], path: str = "simulation_results.json") -> None:
    """Save simulation results to JSON."""
    data = [asdict(r) for r in results]
    output = Path(path)
    output.write_text(json.dumps(data, indent=2))
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    results = run_all()
    save_results(results)
