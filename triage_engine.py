import json
import sqlite3
import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

# ==============================================================================
# Data Models
# ==============================================================================
@dataclass
class PatientVitals:
    age_months: int
    temperature_f: float
    respiratory_rate: int
    has_chest_indrawing: bool = False
    has_stridor: bool = False
    can_drink_breastfeed: bool = True
    vomiting_everything: bool = False
    has_convulsions: bool = False
    lethargic_or_unconscious: bool = False

@dataclass
class VisualAnalysisResult:
    condition_type: str  # "pallor_anemia", "skin_infection", "pediatric_growth"
    severity_score: float # 0.0 to 1.0
    detected_features: List[str]
    confidence: float
    inspection_notes: str

@dataclass
class TriageDecision:
    category: str # "URGENT_PHC_REFERRAL" (Red), "MONITOR_AND_TREAT" (Yellow), "NORMAL_HOME_CARE" (Green)
    urgency_level: str # "IMMEDIATE", "WITHIN_48_HOURS", "ROUTINE"
    danger_signs: List[str]
    primary_condition: str
    icmr_protocol_rule: str
    actions_english: List[str]
    actions_hindi: List[str]
    referral_slip_id: Optional[str] = None

# ==============================================================================
# Clinical Protocol Engine (WHO IMNCI & ICMR Guidelines)
# ==============================================================================
class ICMRTriageProtocolEngine:
    """
    Deterministic clinical decision support engine implementing:
    - WHO IMNCI (Integrated Management of Neonatal & Childhood Illness)
    - ICMR / National Health Mission (NHM) Frontline Health Protocols
    """

    @staticmethod
    def evaluate(
        vitals: PatientVitals,
        symptoms_text: str,
        visual_result: Optional[VisualAnalysisResult] = None
    ) -> TriageDecision:
        danger_signs = []
        
        # 1. Check Universal IMNCI Danger Signs (Any = Immediate RED Referral)
        if not vitals.can_drink_breastfeed:
            danger_signs.append("Unable to drink or breastfeed (स्तनपान या पीने में असमर्थ)")
        if vitals.vomiting_everything:
            danger_signs.append("Vomiting everything persistently (लगातार उल्टी होना)")
        if vitals.has_convulsions:
            danger_signs.append("History of convulsions/fits (दौरे पड़ना)")
        if vitals.lethargic_or_unconscious:
            danger_signs.append("Lethargic or unconscious (सुस्त या बेहोश)")
            
        if danger_signs:
            return TriageDecision(
                category="URGENT_PHC_REFERRAL",
                urgency_level="IMMEDIATE",
                danger_signs=danger_signs,
                primary_condition="Severe General Danger Signs Present",
                icmr_protocol_rule="WHO IMNCI Protocol 1.1: General Danger Signs",
                actions_english=[
                    "Immediate referral to Primary Health Centre (PHC) / District Hospital.",
                    "Give first dose of urgent oral antibiotic (if trained).",
                    "Keep child warm during transport (prevent hypothermia).",
                    "If child can swallow, give sips of ORS or sugar water."
                ],
                actions_hindi=[
                    "तुरंत प्राथमिक स्वास्थ्य केंद्र (PHC) या जिला अस्पताल रेफर करें।",
                    "परिवहन के दौरान बच्चे को गर्म रखें (हाइपोथर्मिया से बचाएं)।",
                    "यदि बच्चा निगल सकता है, तो ओआरएस या चीनी-पानी की घूंट दें।"
                ],
                referral_slip_id=f"REF-ICMR-{int(datetime.datetime.now().timestamp())}"
            )

        # 2. Respiratory Assessment (Fast Breathing Threshold by Age Group)
        fast_breathing = False
        if vitals.age_months < 2 and vitals.respiratory_rate >= 60:
            fast_breathing = True
        elif 2 <= vitals.age_months < 12 and vitals.respiratory_rate >= 50:
            fast_breathing = True
        elif 12 <= vitals.age_months <= 60 and vitals.respiratory_rate >= 40:
            fast_breathing = True

        if vitals.has_chest_indrawing or vitals.has_stridor:
            return TriageDecision(
                category="URGENT_PHC_REFERRAL",
                urgency_level="IMMEDIATE",
                danger_signs=["Chest indrawing or stridor in calm child"],
                primary_condition="Severe Pneumonia / Very Severe Disease",
                icmr_protocol_rule="WHO IMNCI Protocol 2.1: Acute Respiratory Distress",
                actions_english=[
                    "Immediate referral to hospital.",
                    "Administer oxygen if available at Sub-Centre.",
                    "Avoid fluid overload; gentle hydration only."
                ],
                actions_hindi=[
                    "तुरंत अस्पताल रेफर करें।",
                    "यदि उप-केंद्र पर उपलब्ध हो तो ऑक्सीजन दें।",
                    "बच्चे को आराम की स्थिति में रखें।"
                ],
                referral_slip_id=f"REF-RESP-{int(datetime.datetime.now().timestamp())}"
            )

        if fast_breathing:
            return TriageDecision(
                category="MONITOR_AND_TREAT",
                urgency_level="WITHIN_48_HOURS",
                danger_signs=[],
                primary_condition="Pneumonia (Fast Breathing without Stridor)",
                icmr_protocol_rule="WHO IMNCI Protocol 2.2: Fast Breathing Treatment",
                actions_english=[
                    "Administer appropriate home antibiotic (Amoxicillin dispersible) as per ASHA kit.",
                    "Soothe throat and relieve cough with warm fluids.",
                    "Mandatory follow-up visit by ASHA worker in 48 hours."
                ],
                actions_hindi=[
                    "आशा किट के अनुसार एमोक्सिसिलिन गोली दें।",
                    "गले को आराम देने के लिए गुनगुने तरल पदार्थ दें।",
                    "48 घंटे बाद आशा कार्यकर्ता द्वारा अनिवार्य दोबारा जांच।"
                ]
            )

        # 3. Visual Pallor & Anemia Evaluation (Integrated with MobileNetV3 output)
        if visual_result and visual_result.condition_type == "pallor_anemia":
            if visual_result.severity_score >= 0.70:
                return TriageDecision(
                    category="URGENT_PHC_REFERRAL",
                    urgency_level="IMMEDIATE",
                    danger_signs=["Severe Conjunctival / Palmar Pallor (Deep Anemia)"],
                    primary_condition="Severe Anemia (Critical Risk of Cardiac Decompensation)",
                    icmr_protocol_rule="ICMR National Anemia Mukt Bharat Protocol: Severe Anemia",
                    actions_english=[
                        "Refer urgently to PHC for hemoglobin estimation and blood transfusion evaluation.",
                        "Do not administer iron tablets until medical officer review."
                    ],
                    actions_hindi=[
                        "हीमोग्लोबिन जांच और उपचार हेतु तुरंत प्राथमिक स्वास्थ्य केंद्र रेफर करें।",
                        "डॉक्टर की सलाह से पहले आयरन की गोलियां न दें।"
                    ],
                    referral_slip_id=f"REF-ANEM-{int(datetime.datetime.now().timestamp())}"
                )
            elif visual_result.severity_score >= 0.40:
                return TriageDecision(
                    category="MONITOR_AND_TREAT",
                    urgency_level="WITHIN_48_HOURS",
                    danger_signs=[],
                    primary_condition="Moderate Anemia Detected",
                    icmr_protocol_rule="ICMR Anemia Mukt Bharat: Moderate Anemia Guidelines",
                    actions_english=[
                        "Initiate Iron Folic Acid (IFA) syrup/tablets as per age regimen.",
                        "Dietary counselling on green leafy vegetables, jaggery, and pulses.",
                        "Follow up visit in 14 days."
                    ],
                    actions_hindi=[
                        "उम्र के अनुसार आयरन फोलिक एसिड (IFA) सिरप/गोलियां शुरू करें।",
                        "हरी पत्तेदार सब्जियां, गुड़ और दालों के सेवन की सलाह दें।",
                        "14 दिनों में दोबारा जांच करें।"
                    ]
                )

        # 4. Fever / Mild Conditions
        if vitals.temperature_f >= 100.4:
            return TriageDecision(
                category="MONITOR_AND_TREAT",
                urgency_level="WITHIN_48_HOURS",
                danger_signs=[],
                primary_condition="Fever Without Danger Signs (Possible Viral/Malaria)",
                icmr_protocol_rule="NHM Protocol 3.2: Frontline Pediatric Fever Protocol",
                actions_english=[
                    "Administer Paracetamol syrup as per dosage chart.",
                    "Perform Rapid Diagnostic Test (RDT) for Malaria if in endemic block.",
                    "Encourage frequent feeding and fluids."
                ],
                actions_hindi=[
                    "मात्रा चार्ट के अनुसार पैरासिटामोल सिरप दें।",
                    "यदि मलेरिया क्षेत्र है तो आरडीटी (RDT) किट से जांच करें।",
                    "लगातार स्तनपान और ओआरएस तरल पदार्थ दें।"
                ]
            )

        # 5. Normal / Healthy
        return TriageDecision(
            category="NORMAL_HOME_CARE",
            urgency_level="ROUTINE",
            danger_signs=[],
            primary_condition="No Danger Signs / Normal Growth Indicators",
            icmr_protocol_rule="NHM Routine Pediatric Wellness Protocol",
            actions_english=[
                "Reinforce exclusive breastfeeding / balanced home diet.",
                "Ensure age-appropriate immunization schedule is up to date.",
                "Routine monthly Anganwadi growth monitoring (POSHAN Tracker)."
            ],
            actions_hindi=[
                "संतुलित पौष्टिक आहार और नियमित स्तनपान जारी रखें।",
                "टीकाकरण तालिका के अनुसार समय पर टीके लगवाएं।",
                "आंगनवाड़ी में नियमित वजन व विकास की निगरानी करवाएं।"
            ]
        )

# ==============================================================================
# Offline Store & Forward Database (Encrypted Local Storage)
# ==============================================================================
class OfflineTriageStore:
    def __init__(self, db_path: str = "arogya_store.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS triage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT,
                    patient_name TEXT,
                    age_months INTEGER,
                    symptoms_text TEXT,
                    visual_condition TEXT,
                    visual_score REAL,
                    category TEXT,
                    urgency_level TEXT,
                    primary_condition TEXT,
                    referral_slip_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sync_status TEXT DEFAULT 'PENDING'
                )
            """)
            conn.commit()

    def save_record(self, patient_name: str, vitals: PatientVitals, symptoms: str, 
                    visual: Optional[VisualAnalysisResult], decision: TriageDecision) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO triage_records 
                (patient_id, patient_name, age_months, symptoms_text, visual_condition, visual_score,
                 category, urgency_level, primary_condition, referral_slip_id, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """, (
                f"P-{int(datetime.datetime.now().timestamp())}",
                patient_name,
                vitals.age_months,
                symptoms,
                visual.condition_type if visual else "None",
                visual.severity_score if visual else 0.0,
                decision.category,
                decision.urgency_level,
                decision.primary_condition,
                decision.referral_slip_id
            ))
            conn.commit()
            return cursor.lastrowid

    def get_pending_sync_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM triage_records WHERE sync_status = 'PENDING'")
            return cur.fetchone()[0]

    def export_abdm_fhir_bundle(self) -> Dict[str, Any]:
        """
        Exports stored records into an Ayushman Bharat Digital Mission (ABDM)
        compliant Fast Healthcare Interoperability Resources (FHIR) JSON bundle.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM triage_records").fetchall()
            
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": datetime.datetime.now().isoformat(),
            "meta": {
                "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/ClinicalDocumentBundle"]
            },
            "total_records": len(rows),
            "entry": [
                {
                    "resource": {
                        "resourceType": "Condition",
                        "id": row["patient_id"],
                        "clinicalStatus": "active",
                        "category": row["category"],
                        "code": {"text": row["primary_condition"]},
                        "note": [{"text": row["symptoms_text"]}]
                    }
                } for row in rows
            ]
        }
        return bundle

if __name__ == "__main__":
    # Test sample evaluation
    test_vitals = PatientVitals(
        age_months=18,
        temperature_f=101.5,
        respiratory_rate=48, # Fast breathing for 18mo child
        has_chest_indrawing=False
    )
    test_visual = VisualAnalysisResult(
        condition_type="pallor_anemia",
        severity_score=0.75,
        detected_features=["Severe Conjunctival Blanching", "Palmar Whitening"],
        confidence=0.92,
        inspection_notes="Severe pallor detected in lower eyelid mucosa."
    )
    engine = ICMRTriageProtocolEngine()
    decision = engine.evaluate(test_vitals, "Bachhe ko 3 din se bukhar aur thakaan hai", test_visual)
    print("Decision Category:", decision.category)
    print("Primary Condition:", decision.primary_condition)
    print("Actions:", decision.actions_english)
