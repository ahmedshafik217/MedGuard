"""Run once to set up the database: creates all tables, creates the first
owner/admin account (from OWNER_USERNAME / OWNER_PASSWORD in .env), and
seeds a starting reference list of common antibiotics.

    python seed.py

IMPORTANT: the antibiotic reference data below is a general pharmacology
starting point (pregnancy notes, allergy classes, common contraindications)
meant to save the owner typing. Before this is relied on for real patients,
a licensed pharmacist or physician on staff MUST review, correct, and keep
current every entry from the Owner Dashboard -> Antibiotic Reference
Database screen. Do not treat the seed data as medical advice.
"""
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app import models  # noqa: E402

REFERENCE_ANTIBIOTICS = [
    # generic_name, brand_names, drug_class, pregnancy_contraindicated,
    # pregnancy_notes, contraindicated_conditions, notes
    ("Amoxicillin", "Amoxil", "Penicillin", False,
     "Generally considered safe in pregnancy.",
     ["Penicillin allergy", "Infectious mononucleosis"], None),
    ("Amoxicillin-Clavulanate", "Augmentin", "Penicillin", False,
     "Generally considered safe in pregnancy.",
     ["Penicillin allergy", "Cholestatic jaundice / liver disease history"], None),
    ("Ampicillin", "", "Penicillin", False,
     "Generally considered safe in pregnancy.",
     ["Penicillin allergy"], None),
    ("Penicillin V", "", "Penicillin", False,
     "Generally considered safe in pregnancy.",
     ["Penicillin allergy"], None),
    ("Cephalexin", "Keflex", "Cephalosporin", False,
     "Generally considered safe in pregnancy.",
     ["Cephalosporin allergy", "Severe penicillin allergy (anaphylaxis)"], None),
    ("Ceftriaxone", "Rocephin", "Cephalosporin", False,
     "Generally considered safe in pregnancy.",
     ["Cephalosporin allergy", "Hyperbilirubinemia (neonates)"], None),
    ("Cefuroxime", "Zinacef", "Cephalosporin", False,
     "Generally considered safe in pregnancy.",
     ["Cephalosporin allergy"], None),
    ("Azithromycin", "Zithromax", "Macrolide", False,
     "Considered relatively safe in pregnancy when indicated.",
     ["Macrolide allergy", "QT prolongation / long QT syndrome", "Liver disease"], None),
    ("Clarithromycin", "Biaxin", "Macrolide", True,
     "Avoid in pregnancy when possible; prefer azithromycin — some studies link it to "
     "miscarriage/birth defect risk.",
     ["Macrolide allergy", "QT prolongation / long QT syndrome"], None),
    ("Erythromycin", "", "Macrolide", False,
     "Base form generally used in pregnancy; avoid the estolate salt (liver toxicity).",
     ["Macrolide allergy", "Liver disease", "QT prolongation / long QT syndrome"], None),
    ("Doxycycline", "Vibramycin", "Tetracycline", True,
     "Avoid in pregnancy and in children under 8 — tooth discoloration and bone growth effects.",
     ["Tetracycline allergy", "Severe liver disease"], None),
    ("Tetracycline", "", "Tetracycline", True,
     "Avoid in pregnancy and in children under 8 — tooth discoloration and bone growth effects.",
     ["Tetracycline allergy", "Severe liver disease"], None),
    ("Minocycline", "", "Tetracycline", True,
     "Avoid in pregnancy and in children under 8 — tooth discoloration and bone growth effects.",
     ["Tetracycline allergy"], None),
    ("Ciprofloxacin", "Cipro", "Fluoroquinolone", True,
     "Avoid in pregnancy unless no safer alternative exists — animal studies show arthropathy risk.",
     ["Fluoroquinolone allergy", "Myasthenia gravis", "QT prolongation / long QT syndrome",
      "Tendon disorders / previous tendon rupture", "Epilepsy / seizure disorder"], None),
    ("Levofloxacin", "Levaquin", "Fluoroquinolone", True,
     "Avoid in pregnancy unless no safer alternative exists.",
     ["Fluoroquinolone allergy", "Myasthenia gravis", "QT prolongation / long QT syndrome",
      "Tendon disorders / previous tendon rupture", "Epilepsy / seizure disorder"], None),
    ("Moxifloxacin", "Avelox", "Fluoroquinolone", True,
     "Avoid in pregnancy unless no safer alternative exists.",
     ["Fluoroquinolone allergy", "Myasthenia gravis", "QT prolongation / long QT syndrome",
      "Tendon disorders / previous tendon rupture"], None),
    ("Gentamicin", "", "Aminoglycoside", True,
     "Avoid unless benefit outweighs risk of fetal ototoxicity; requires level monitoring.",
     ["Aminoglycoside allergy", "Myasthenia gravis", "Renal impairment / kidney disease",
      "Hearing loss / vestibular disorder"], None),
    ("Amikacin", "", "Aminoglycoside", True,
     "Avoid unless benefit outweighs risk of fetal ototoxicity; requires level monitoring.",
     ["Aminoglycoside allergy", "Myasthenia gravis", "Renal impairment / kidney disease",
      "Hearing loss / vestibular disorder"], None),
    ("Trimethoprim-Sulfamethoxazole", "Bactrim, Septrin", "Sulfonamide", True,
     "Avoid in the first trimester (neural tube defect risk) and near term (neonatal kernicterus risk).",
     ["Sulfonamide allergy", "G6PD deficiency", "Severe liver disease",
      "Megaloblastic anemia / folate deficiency"], None),
    ("Nitrofurantoin", "Macrobid, Macrodantin", "Nitrofuran", False,
     "Commonly used for UTI in pregnancy, but avoid near term (38-42 weeks) and during labor "
     "— risk of neonatal hemolytic anemia.",
     ["G6PD deficiency"], None),
    ("Metronidazole", "Flagyl", "Nitroimidazole", False,
     "Widely used in pregnancy when indicated; confirm against your current local protocol "
     "for first-trimester use.",
     ["Metronidazole allergy", "Severe liver disease", "Alcohol use disorder"], None),
    ("Clindamycin", "Cleocin", "Lincosamide", False,
     "Generally considered safe in pregnancy.",
     ["Clindamycin allergy", "Inflammatory bowel disease", "History of C. difficile colitis"], None),
    ("Vancomycin", "", "Glycopeptide", False,
     "Used in pregnancy when clinically indicated (e.g. serious Gram-positive infection).",
     ["Vancomycin allergy", "Renal impairment / kidney disease", "Hearing loss / vestibular disorder"], None),
    ("Meropenem", "Merrem", "Carbapenem", False,
     "Used in pregnancy when clinically indicated.",
     ["Carbapenem allergy", "Penicillin allergy (cross-reactivity risk)", "Epilepsy / seizure disorder"], None),
    ("Imipenem-Cilastatin", "Primaxin", "Carbapenem", False,
     "Used in pregnancy when clinically indicated.",
     ["Carbapenem allergy", "Epilepsy / seizure disorder"], None),
    ("Chloramphenicol", "", "Amphenicol", True,
     "Avoid, especially near term — risk of neonatal 'gray baby syndrome'.",
     ["Chloramphenicol allergy", "G6PD deficiency", "Bone marrow suppression / blood disorder"], None),
    ("Linezolid", "Zyvox", "Oxazolidinone", False,
     "Limited pregnancy data — use only if benefit outweighs risk and no alternative exists.",
     ["Linezolid allergy", "Uncontrolled hypertension", "Taking MAOIs or serotonergic medications"], None),
    ("Rifampin", "Rifadin", "Rifamycin", False,
     "Generally continued in pregnancy when treating tuberculosis; discuss with specialist.",
     ["Rifampin allergy", "Liver disease"], None),
    ("Fosfomycin", "Monurol", "Phosphonic acid derivative", False,
     "Considered an option for UTI in pregnancy.",
     ["Fosfomycin allergy"], None),
]


def run():
    app = create_app()
    with app.app_context():
        if models.count_antibiotics() == 0:
            for (generic, brands, drug_class, preg_contra, preg_notes, conditions, notes) in REFERENCE_ANTIBIOTICS:
                models.add_antibiotic(
                    generic_name=generic,
                    brand_names=brands or None,
                    drug_class=drug_class,
                    pregnancy_contraindicated=preg_contra,
                    pregnancy_notes=preg_notes,
                    contraindicated_conditions=conditions,
                    notes=notes,
                )
            print(f"Seeded {len(REFERENCE_ANTIBIOTICS)} reference antibiotics.")
        else:
            print("Antibiotic reference table already has data — skipped seeding it.")

        username = app.config["OWNER_USERNAME"]
        if not models.get_owner_by_username(username):
            models.create_owner(username, app.config["OWNER_PASSWORD"])
            print(f"Created owner account '{username}'. CHANGE THIS PASSWORD after first login.")
        else:
            print(f"Owner account '{username}' already exists — skipped.")


if __name__ == "__main__":
    run()
