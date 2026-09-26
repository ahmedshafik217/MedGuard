"""Run once to set up the database: creates all tables, creates the first
owner/admin account (from OWNER_USERNAME / OWNER_PASSWORD in .env), and
seeds starting reference lists: common antibiotics, common "other
medications" (generic + brand names), and well-established antibiotic/drug
interactions between the two.

    python seed.py

This also runs automatically on every container start (see
docker-entrypoint.sh) -- most hosting tiers can restart/redeploy the
container at any time, so the app has to be able to fully re-initialize
itself every time it boots rather than relying on a one-time manual step.
Every seeding step below is idempotent (checked against what's already in
the database before inserting), so re-running this against a live database
that already has real data -- including anything added by hand from the
Owner Dashboard -- never duplicates or overwrites it.

IMPORTANT: all of the reference data below (antibiotics, medications, and
especially the drug interactions) is a general pharmacology starting point
meant to save the owner typing, not a complete or final clinical reference.
Before this is relied on for real patients, a licensed pharmacist or
physician on staff MUST review, correct, and keep current every entry from
the Owner Dashboard's reference-database screens (Antibiotic Reference,
Medications Reference, Drug Interactions Reference). Do not treat the seed
data as medical advice.
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

# Common "other" (non-antibiotic) medications, generic name + brand names --
# see app/db.py's medications_reference table. Each is one a patient might
# plausibly self-record (or have scanned from a package) under its BRAND
# name, so having it here lets that resolve to the same generic name the
# interactions below are written against (see app/engine/safety_check.py).
# Seeded item-by-item (not gated on the whole table being empty) since the
# owner may have already added their own entries by hand.
REFERENCE_MEDICATIONS = [
    # generic_name, brand_names
    ("Warfarin", "Coumadin, Jantoven"),
    ("Theophylline", "Theo-24, Uniphyl"),
    ("Tizanidine", "Zanaflex"),
    ("Simvastatin", "Zocor"),
    ("Atorvastatin", "Lipitor"),
    ("Colchicine", "Colcrys"),
    ("Digoxin", "Lanoxin"),
    ("Lithium", "Lithobid, Eskalith"),
    ("Methotrexate", "Trexall, Otrexup"),
    ("Lisinopril", "Zestril, Prinivil"),
    ("Glipizide", "Glucotrol"),
    ("Tacrolimus", "Prograf"),
    ("Calcium Carbonate", "Tums, Caltrate"),
    ("Ferrous Sulfate", "Feosol, Slow Fe"),
    ("Furosemide", "Lasix"),
    ("Sertraline", "Zoloft"),
    ("Fluoxetine", "Prozac"),
]

# Well-established, textbook-level antibiotic/drug interactions -- matched
# against either a whole antibiotic_class (applies to every drug in that
# class, e.g. every Fluoroquinolone) or one specific antibiotic_name, the
# same either/or the Owner Dashboard's "Add drug interaction" form itself
# offers. Deliberately limited to interactions that are (a) well known
# enough that essentially every pharmacology reference agrees on them, and
# (b) relevant to an antibiotic class/name already in REFERENCE_ANTIBIOTICS
# above -- not every antibiotic class has a "must-know" interaction, so
# several are intentionally left without an entry here; add more from the
# Owner Dashboard as needed. Seeded item-by-item, matched on
# (antibiotic_name or antibiotic_class, interacting_drug) so re-running
# this never creates a duplicate of a row the owner already added by hand
# (whether seeded before, or typed in manually).
REFERENCE_DRUG_INTERACTIONS = [
    # antibiotic_name, antibiotic_class, interacting_drug, severity,
    # category_label, mechanism, management
    (None, "Fluoroquinolone", "Warfarin", "danger", "Anticoagulant",
     "Fluoroquinolones can inhibit warfarin metabolism, increasing INR and bleeding risk.",
     "Monitor INR closely for several days after starting/stopping; adjust warfarin dose as needed."),
    (None, "Fluoroquinolone", "Theophylline", "danger", "Bronchodilator / Methylxanthine",
     "Ciprofloxacin especially inhibits CYP1A2, raising theophylline levels -- risk of nausea, seizures, arrhythmia.",
     "Avoid the combination if possible; if necessary, monitor theophylline levels and reduce the dose."),
    (None, "Fluoroquinolone", "Tizanidine", "danger", "Muscle relaxant",
     "Fluoroquinolones (especially ciprofloxacin) markedly increase tizanidine levels via CYP1A2 inhibition, "
     "causing severe hypotension and sedation.",
     "Avoid the combination."),
    (None, "Macrolide", "Simvastatin", "danger", "Statin",
     "Clarithromycin/erythromycin strongly inhibit CYP3A4, raising statin levels and myopathy/rhabdomyolysis "
     "risk. (Azithromycin has minimal CYP3A4 effect.)",
     "Hold the statin during the antibiotic course, or use azithromycin instead if a macrolide is required."),
    (None, "Macrolide", "Atorvastatin", "warning", "Statin",
     "Clarithromycin/erythromycin raise atorvastatin levels via CYP3A4 inhibition, increasing myopathy risk.",
     "Consider a temporary statin hold, or use azithromycin instead if a macrolide is needed."),
    (None, "Macrolide", "Warfarin", "warning", "Anticoagulant",
     "Macrolides can inhibit warfarin metabolism, increasing INR.",
     "Monitor INR during and after the antibiotic course."),
    (None, "Macrolide", "Colchicine", "danger", "Gout medication",
     "Clarithromycin strongly inhibits colchicine metabolism/clearance, risking severe, sometimes fatal, "
     "colchicine toxicity.",
     "Avoid the combination, especially in renal/hepatic impairment; reduce the colchicine dose or choose a "
     "different antibiotic."),
    (None, "Macrolide", "Digoxin", "warning", "Cardiac glycoside",
     "Macrolides can raise digoxin levels (altered gut flora / P-glycoprotein effects), risking digoxin toxicity.",
     "Monitor digoxin levels/symptoms during treatment."),
    ("Metronidazole", None, "Warfarin", "danger", "Anticoagulant",
     "Metronidazole inhibits warfarin metabolism, significantly increasing INR and bleeding risk.",
     "Monitor INR closely; anticipate a warfarin dose reduction."),
    ("Metronidazole", None, "Alcohol", "danger", "Disulfiram-like reaction",
     "Metronidazole can cause a disulfiram-like reaction with alcohol (flushing, nausea, vomiting, palpitations).",
     "Counsel the patient to avoid all alcohol during treatment and for 48 hours after the last dose."),
    ("Metronidazole", None, "Lithium", "warning", "Mood stabilizer",
     "Metronidazole can reduce lithium clearance, raising lithium levels.",
     "Monitor lithium levels if co-administered."),
    ("Trimethoprim-Sulfamethoxazole", None, "Warfarin", "danger", "Anticoagulant",
     "Trimethoprim-sulfamethoxazole inhibits warfarin metabolism and displaces it from protein binding, "
     "increasing INR.",
     "Monitor INR closely; consider an alternative antibiotic if possible."),
    ("Trimethoprim-Sulfamethoxazole", None, "Methotrexate", "danger", "Antimetabolite / DMARD",
     "Both drugs inhibit folate metabolism; combination risks severe bone marrow suppression.",
     "Avoid the combination when possible; monitor blood counts closely if unavoidable."),
    ("Trimethoprim-Sulfamethoxazole", None, "Lisinopril", "warning", "ACE inhibitor",
     "Trimethoprim behaves like a potassium-sparing diuretic; combined with ACE inhibitors this raises "
     "hyperkalemia risk.",
     "Monitor serum potassium, especially in renal impairment or the elderly."),
    ("Trimethoprim-Sulfamethoxazole", None, "Glipizide", "warning", "Sulfonylurea",
     "Trimethoprim-sulfamethoxazole can potentiate sulfonylureas, risking hypoglycemia.",
     "Monitor blood glucose closely during co-administration."),
    ("Rifampin", None, "Oral Contraceptives", "danger", "Hormonal contraceptive",
     "Rifampin strongly induces hepatic enzymes, reducing contraceptive hormone levels and effectiveness.",
     "Advise a non-hormonal backup contraceptive method during and for at least 4 weeks after rifampin."),
    ("Rifampin", None, "Warfarin", "warning", "Anticoagulant",
     "Rifampin induces warfarin metabolism, REDUCING INR/anticoagulant effect -- the opposite direction from "
     "most other antibiotic interactions above.",
     "Monitor INR closely; warfarin dose often needs to be increased during rifampin therapy and reduced "
     "again after stopping it."),
    ("Rifampin", None, "Tacrolimus", "danger", "Immunosuppressant",
     "Rifampin induces tacrolimus metabolism, sharply reducing its levels and risking transplant rejection.",
     "Avoid the combination if possible; if unavoidable, monitor tacrolimus levels closely with dose adjustment."),
    (None, "Tetracycline", "Calcium Carbonate", "warning", "Antacid / Supplement",
     "Calcium chelates tetracyclines in the gut, reducing antibiotic absorption.",
     "Separate dosing by at least 2-3 hours."),
    (None, "Tetracycline", "Ferrous Sulfate", "warning", "Iron supplement",
     "Iron chelates tetracyclines in the gut, reducing antibiotic absorption.",
     "Separate dosing by at least 2-3 hours."),
    (None, "Aminoglycoside", "Furosemide", "danger", "Loop diuretic",
     "Both are independently oto/nephrotoxic; combination increases risk of hearing loss and kidney injury.",
     "Avoid the combination when possible; monitor renal function and hearing if unavoidable."),
    ("Linezolid", None, "Sertraline", "danger", "SSRI / Serotonergic",
     "Linezolid has weak MAO-inhibitor activity; combined with serotonergic drugs it risks serotonin syndrome.",
     "Avoid the combination; if unavoidable, monitor closely for serotonin syndrome symptoms (agitation, "
     "tremor, hyperthermia)."),
    ("Linezolid", None, "Fluoxetine", "danger", "SSRI / Serotonergic",
     "Same serotonin syndrome risk as with other SSRIs/SNRIs.",
     "Avoid the combination; if unavoidable, monitor closely for serotonin syndrome symptoms."),
    (None, "Penicillin", "Methotrexate", "warning", "Antimetabolite / DMARD",
     "Penicillins can reduce renal clearance of methotrexate, raising methotrexate levels and toxicity risk.",
     "Monitor for methotrexate toxicity (mucositis, cytopenias) if co-administered, especially at high-dose "
     "methotrexate regimens."),
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

        added_meds = 0
        for (generic, brands) in REFERENCE_MEDICATIONS:
            if not models.get_medication_reference_by_name(generic):
                models.add_medication_reference(generic_name=generic, brand_names=brands or None)
                added_meds += 1
        if added_meds:
            print(f"Seeded {added_meds} new reference medications (skipped any already on file).")
        else:
            print("Reference medications already on file — nothing new to seed.")

        existing_interactions = {
            ((row.get("antibiotic_name") or "").strip().lower(),
             (row.get("antibiotic_class") or "").strip().lower(),
             (row.get("interacting_drug") or "").strip().lower())
            for row in models.list_drug_interactions()
        }
        added_interactions = 0
        for (antibiotic_name, antibiotic_class, interacting_drug, severity,
             category_label, mechanism, management) in REFERENCE_DRUG_INTERACTIONS:
            key = ((antibiotic_name or "").strip().lower(),
                   (antibiotic_class or "").strip().lower(),
                   (interacting_drug or "").strip().lower())
            if key in existing_interactions:
                continue
            models.add_drug_interaction(
                interacting_drug=interacting_drug,
                severity=severity,
                antibiotic_name=antibiotic_name,
                antibiotic_class=antibiotic_class,
                category_label=category_label,
                mechanism=mechanism,
                management=management,
            )
            existing_interactions.add(key)
            added_interactions += 1
        if added_interactions:
            print(f"Seeded {added_interactions} new reference drug interactions (skipped any already on file).")
        else:
            print("Reference drug interactions already on file — nothing new to seed.")

        username = app.config["OWNER_USERNAME"]
        if not models.get_owner_by_username(username):
            models.create_owner(username, app.config["OWNER_PASSWORD"])
            print(f"Created owner account '{username}'. CHANGE THIS PASSWORD after first login.")
        else:
            print(f"Owner account '{username}' already exists — skipped.")


if __name__ == "__main__":
    run()
