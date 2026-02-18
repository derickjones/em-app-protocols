# Gemini vs RAG Comparison Results

**Test Date:** February 17, 2026
**System Prompt:** "You are a clinical decision support tool for emergency medicine physicians meant to give them useful advice at the bedside."

---

## Query 1: Pharmacology/Dosing

**Question:** What are the contraindications and dosing for tPA in acute ischemic stroke?

### Gemini Response

Clinical Decision Support: tPA (Alteplase) for Acute Ischemic Stroke

**Bottom Line Up Front:** Treatment window is 0–3 hours (standard) or 3–4.5 hours (extended/ECASS III) from "Last Known Well." Strict Blood Pressure control is required prior to and during administration.

**1. Dosing Protocols**
- **Standard: Alteplase (tPA)**
  - Total Dose: 0.9 mg/kg (Maximum total dose: 90 mg)
  - Administration:
    - Bolus: Give 10% of the total dose IV push over 1 minute.
    - Infusion: Give the remaining 90% IV over 60 minutes.
  - Prep: Reconstitute with sterile water without preservatives. Do not shake.

- **Alternative: Tenecteplase (TNK)**
  - Dose: 0.25 mg/kg IV Bolus (Maximum dose: 25 mg).
  - Administration: Single IV bolus over 5 seconds.

**2. Absolute Contraindications (DO NOT TREAT)**
- Hemorrhage: Any history of Intracranial Hemorrhage (ICH)
- Active Bleeding: Internal bleeding (GI/GU) or acute trauma/fracture
- Recent Surgery/Trauma: Significant head trauma or intracranial/spinal surgery within 3 months
- Malignancy: Intracranial neoplasm, AVM, or aneurysm
- Coagulopathy:
  - Platelets < 100,000
  - INR > 1.7 or PT > 15s
  - DOAC Use within 48 hours
- CT Findings: Evidence of extensive infarction (hypodensity > 1/3 cerebral hemisphere)
- Blood Pressure: SBP > 185 mmHg or DBP > 110 mmHg that is refractory

**3. The 3.0 – 4.5 Hour Window (Additional Exclusions)**
- Age: > 80 years old
- Stroke Severity: NIHSS score > 25
- History: History of BOTH Diabetes AND prior Stroke
- Anticoagulation: Any oral anticoagulant use (regardless of INR)

**4. Blood Pressure Goals (Safety Critical)**
- Pre-TPA: < 185 / 110
- Post-TPA: < 180 / 105

### Your RAG Response

[PASTE YOUR RAG RESPONSE HERE]

### Comparison Analysis

**Format & Structure:**
- Gemini: ✅ Excellent use of headers, clear sections, table format for BP goals
- Gemini: ✅ "Bottom Line Up Front" summary - immediately actionable
- Gemini: ✅ Clear categorization (Absolute vs Relative contraindications)
- Gemini: ✅ Numbered sections for easy navigation
- Your RAG: [YOUR NOTES]

**Conciseness:**
- Gemini: ~300 words, very scannable
- Your RAG: [WORD COUNT]

**Actionability:**
- Gemini: ✅ Dosing clearly stated upfront
- Gemini: ✅ "DO NOT TREAT" emphasis on contraindications
- Gemini: ✅ BP goals in table format
- Your RAG: [YOUR NOTES]

**Citations/Sources:**
- Gemini: ❌ No citations
- Your RAG: ✅ [LIST CITATIONS - should include WikEM, PMC sources]

**Images:**
- Gemini: ❌ No images
- Your RAG: [ANY IMAGES?]

**Medical Accuracy:**
- Gemini: [YOUR ASSESSMENT]
- Your RAG: [YOUR ASSESSMENT]

**Winner for Bedside Use:** [GEMINI or RAG or TIE]

**Key Improvements to Implement:**
1. 
2. 
3. 

---

## Query 2: High-Acuity Clinical

**Question:** How do I manage undifferentiated shock in a hypotensive patient?

### Gemini Response

**Bottom Line Up Front:** In undifferentiated hypotension, assume Distributive (Sepsis) until proven otherwise, but you must rapidly rule out Obstructive and Cardiogenic causes before flooding the patient with fluids.

**1. Immediate Stabilization ("The Safety Net")**
- Access: Two large-bore peripheral IVs (18G or larger). Do not wait for a central line to start pressors.
- Fluids: Start 500 mL - 1 L Balanced Crystalloid bolus immediately (unless frank pulmonary edema is present).
- Temporizing Pressors: If MAP < 65 mmHg and perfusion is critical, use Push-Dose Epinephrine while setting up the infusion.
  - Mix: Take a 10 mL syringe of normal saline. Discard 1 mL. Draw up 1 mL of Cardiac Epinephrine (1:10,000). Concentration = 10 mcg/mL.
  - Dose: 0.5 – 2 mL (5–20 mcg) every 2–5 minutes.
- First-Line Infusion: Norepinephrine (Levophed). Start at 5–10 mcg/min and titrate rapidly.

**2. The Diagnostic Algorithm: RUSH Exam**
| Component | What to Look For | Clinical Implication |
|-----------|------------------|---------------------|
| THE PUMP (Heart) | Squeeze, Effusion, Strain | Poor Squeeze: Cardiogenic. Tamponade: Obstructive. RV Strain: Massive PE |
| THE TANK (Volume) | IVC, FAST, Lungs | Flat IVC: Hypovolemic/Distributive. Fat IVC: Cardiogenic/Obstructive |
| THE PIPES (Vessels) | Aorta, DVT | AAA: Hemorrhagic. DVT: PE |

**3. Empiric Management by Likely Category**

A. **Distributive (Warm/Vasodilated)**
- Action: 30 mL/kg crystalloid, broad-spectrum antibiotics, consider steroids

B. **Cardiogenic (Cold/Wet)**
- Action: Stop fluids, add Dobutamine or Epinephrine, Cath Lab if STEMI

C. **Obstructive (JVD/Strain)**
- Action: Needle decompression (Tension Pneumo), Pericardiocentesis (Tamponade), Thrombolytics (Massive PE)

D. **Hypovolemic (Cold/Dry)**
- Action: Blood products 1:1:1, source control

**4. Critical Pre-Intubation Warning**
"Resuscitate Before You Intubate." Ensure MAP > 65 mmHg, use Ketamine/Etomidate, reduce dose by 50%.

### Your RAG Response

[PASTE YOUR RAG RESPONSE HERE]

### Comparison Analysis

**Format & Structure:**
- Gemini: [YOUR NOTES]
- Your RAG: [YOUR NOTES]

**Conciseness:**
- Gemini: [WORD COUNT]
- Your RAG: [WORD COUNT]

**Actionability:**
- Gemini: [YOUR NOTES]
- Your RAG: [YOUR NOTES]

**Citations/Sources:**
- Gemini: ❌ No citations
- Your RAG: ✅ [LIST CITATIONS]

**Winner for Bedside Use:** [GEMINI or RAG or TIE]

**Key Improvements to Implement:**
1. 
2. 
3. 

---

## Query 3: Emergency Protocol

**Question:** What's the management for suspected hyperkalemia with EKG changes?

### Gemini Response

**Bottom Line Up Front:** This is a life-threatening medical emergency. EKG changes indicate imminent cardiac arrest. You must Stabilize the Membrane immediately before waiting for labs or shifting potassium.

**1. Step 1: Membrane Stabilization (IMMEDIATE)**
- **Calcium Gluconate:** 3 grams (30 mL of 10% solution) IV push over 2–5 minutes (Peripheral IV preferred)
- **Calcium Chloride:** 1 gram (10 mL of 10% solution) IV push (3x more potent, Central Line preferred)
- Duration: Effect lasts 30–60 minutes. Repeat if EKG changes persist after 5 minutes.

**2. Step 2: Shift Potassium Intracellularly (Fast)**

| Agent | Dosing | Onset | Notes |
|-------|--------|-------|-------|
| Insulin + Dextrose | 10 units Regular Insulin IV + 1 Amp D50 (25g) | 15–30 min | Check glucose q1h |
| Albuterol | 10–20 mg Nebulized | 30 min | 4–8x standard asthma dose |
| Sodium Bicarbonate | 1–2 Amps (50–100 mEq) IV | Varies | For pH < 7.1 only |

**3. Step 3: Eliminate Potassium (Excretion)**
- **Loop Diuretics:** Furosemide 40–80 mg IV (requires urine output)
- **GI Binders:** Lokelma 10g PO (faster than Kayexalate)
- **Hemodialysis:** Definitive treatment for anuric renal failure

**4. EKG Progression Watchlist**
- Peaked T Waves → Prolonged PR → QRS Widening → Sine Wave (Terminal)

### Your RAG Response

[PASTE YOUR RAG RESPONSE HERE]

### Comparison Analysis

**Format & Structure:**
- Gemini: [YOUR NOTES]
- Your RAG: [YOUR NOTES]

**Conciseness:**
- Gemini: [WORD COUNT]
- Your RAG: [WORD COUNT]

**Actionability:**
- Gemini: [YOUR NOTES]
- Your RAG: [YOUR NOTES]

**Citations/Sources:**
- Gemini: ❌ No citations
- Your RAG: ✅ [LIST CITATIONS]

**Winner for Bedside Use:** [GEMINI or RAG or TIE]

**Key Improvements to Implement:**
1. 
2. 
3. 

---

## Query 4: Risk Stratification

**Question:** When can I safely discharge a patient with chest pain after negative troponin?

### Gemini Response

**Bottom Line Up Front:** A negative troponin alone is rarely sufficient for discharge unless the patient is Low Risk on a validated scoring system (like the HEART Score) OR the troponin was drawn > 6 hours after symptom onset with high-sensitivity assays.

**1. The Decision Tool: The HEART Score**
Use this to objectively stratify risk. A score of 0–3 is generally considered "Low Risk" (MACE < 2%).

| Component | 0 Points | 1 Point | 2 Points |
|-----------|----------|---------|----------|
| History | Slightly suspicious | Moderately suspicious | Highly suspicious |
| ECG | Normal | Non-specific changes | Significant ST depression / LBBB / LVH |
| Age | < 45 | 45–65 | > 65 |
| Risk Factors | None | 1–2 | ≥3 or History of CAD |
| Troponin | ≤ Normal | 1–3x Normal | > 3x Normal |

**2. Discharge Protocols by Assay Type**

**A. High-Sensitivity Troponin (hs-cTn)**
- 0-Hour / 1-Hour Algorithm:
  - Rule Out: If initial hs-cTn < 5 ng/L AND onset > 3 hours ago → Discharge
  - Observation: Repeat at 1 hour. If no significant delta → Discharge
- Safety Net: Only if HEART Score ≤ 3 and pain free

**B. Conventional Troponin**
- Serial Testing: Draw at 0 and 3 hours
- If both negative AND pain-free + HEART ≤ 3 → Discharge
- Late Presenters: If onset > 6–12 hours and single negative troponin → Safe discharge if low risk

**3. The "HEART Pathway" (Validated Protocol)**
- **HEART Score 0–3:** Serial troponins (0 and 3h). If negative: Discharge. Follow-up 7–14 days.
- **HEART Score 4–6:** Admit for observation / provocative testing
- **HEART Score 7–10:** Early invasive strategy

**4. "The Deadly Six" Checklist**
Before discharge, rule out: PE, Dissection, Pneumothorax, Boerhaave's, Tamponade, Unstable Angina

### Your RAG Response

[PASTE YOUR RAG RESPONSE HERE]

### Comparison Analysis

**Format & Structure:**
- Gemini: [YOUR NOTES]
- Your RAG: [YOUR NOTES]

**Conciseness:**
- Gemini: [WORD COUNT]
- Your RAG: [WORD COUNT]

**Actionability:**
- Gemini: [YOUR NOTES]
- Your RAG: [YOUR NOTES]

**Citations/Sources:**
- Gemini: ❌ No citations
- Your RAG: ✅ [LIST CITATIONS]

**Winner for Bedside Use:** [GEMINI or RAG or TIE]

**Key Improvements to Implement:**
1. 
2. 
3. 

---

## Query 5: Procedure

**Question:** What are the steps for RSI in a suspected difficult airway?

### Gemini Response

**Bottom Line Up Front:** If a difficult airway is suspected, STOP. The safest airway is an Awake Intubation. If the patient's physiology forces you to proceed with RSI, you must use a "Double Setup" approach.

**1. The "Go / No-Go" Decision**
Ask: "Can I oxygenate this patient with BVM or LMA if I fail to intubate?"
- **NO (Anatomically impossible):** Do NOT paralyze. Proceed to Awake Intubation
- **YES (Rescue possible):** Proceed with Double Setup RSI

**2. The "Double Setup" Protocol (Preparation)**
- **Positioning:** "Ramp" the patient (ear-to-sternal notch alignment)
- **Oxygenation:**
  - Pre-oxygenate: 15L+ Non-Rebreather for 3 minutes
  - Apneic Oxygenation: Nasal Cannula at 15L/min (leave ON)
- **Neck Marking (Critical):**
  - Identify cricothyroid membrane
  - Mark it with a pen
  - Open Cric Kit: #10 scalpel, bougie, 6.0 ETT on bedside table
- **Plan A Equipment:** Video Laryngoscopy (Hyperangulated blade) + Bougie loaded

**3. Drug Selection (Hemodynamically Stable)**
- **Induction:** Ketamine (1.5–2 mg/kg IV) - Preserves respiratory drive
- **Paralysis:** Rocuronium (1.2–1.6 mg/kg IV) - Higher dose for adequate relaxation

**4. The Failed Airway Algorithm (Vortex Approach)**
- **Attempt 1 (Plan A):** Video Laryngoscopy + External Laryngeal Manipulation
- **Attempt 2 (Plan B):** Supraglottic Airway (iGel / LMA)
- **Attempt 3 (Plan C - CICO):** Face Mask Ventilation (2-person technique)
- If SpO2 continues dropping: DECLARE CICO

**5. Plan D: Emergency Front of Neck Access (eFONA)**
Don't wait for cardiac arrest. Cut while there is still a pulse.

**Technique: Scalpel-Bougie-Tube (SBT)**
1. Scalpel: Vertical incision over thyroid → Horizontal stab through cricothyroid membrane → Twist blade 90°
2. Bougie: Slide coude tip down blade into trachea
3. Tube: Railroad 6.0 mm ETT over bougie. Inflate cuff.

### Your RAG Response

[PASTE YOUR RAG RESPONSE HERE]

### Comparison Analysis

**Format & Structure:**
- Gemini: [YOUR NOTES]
- Your RAG: [YOUR NOTES]

**Conciseness:**
- Gemini: [WORD COUNT]
- Your RAG: [WORD COUNT]

**Actionability:**
- Gemini: [YOUR NOTES]
- Your RAG: [YOUR NOTES]

**Citations/Sources:**
- Gemini: ❌ No citations
- Your RAG: ✅ [LIST CITATIONS]

**Winner for Bedside Use:** [GEMINI or RAG or TIE]

**Key Improvements to Implement:**
1. 
2. 
3. 

---

## Overall Summary

### Gemini's Strengths (Observed)
1. **Format:** Clean headers, tables, bold emphasis
2. **Structure:** "Bottom Line Up Front" approach
3. **Organization:** Clear categorization (Absolute vs Relative)
4. **Scanability:** Easy to find critical info quickly
5. **Action-oriented:** DO NOT TREAT, clear dosing upfront

### Your RAG's Strengths (Expected)
1. ✅ **Citations:** WikEM, PMC, LITFL sources with URLs
2. ✅ **Images:** Visual aids from LITFL (once indexed)
3. ✅ **Evidence-based:** Traceable to medical literature
4. ✅ **Liability protection:** Source attribution
5. ✅ **Consistency:** Same sources = same answers

### Top 5 Improvements to Implement in Your RAG

Based on what Gemini does well:

1. **Add "Bottom Line Up Front" summary**
   - 1-2 sentence critical takeaway at the top
   - Example: "Treatment window 0-3h, strict BP control required"

2. **Use bold headers and clear sections**
   - Dosing Protocol
   - Contraindications (DO NOT TREAT)
   - Management Steps

3. **Emphasize critical actions**
   - Bold or ALL CAPS for "DO NOT TREAT"
   - Highlight dosing at the top
   - Clear BP goals/parameters

4. **Use tables for structured data**
   - BP goals (Pre-TPA vs Post-TPA)
   - Dosing tables
   - Timeline criteria

5. **Improve categorization**
   - Absolute vs Relative contraindications
   - Numbered steps for procedures
   - Clear time windows

### Implementation Plan

**Phase 1: Response Formatting (Backend)**
- [ ] Modify RAG prompt to request structured format
- [ ] Add markdown formatting to responses
- [ ] Include "Key Points" summary at top

**Phase 2: Frontend Display**
- [ ] Parse markdown for better rendering
- [ ] Add collapsible sections
- [ ] Highlight critical actions

**Phase 3: Citation Integration**
- [ ] Keep citations but make them less intrusive
- [ ] Add expandable "Sources" section
- [ ] Show citation count without listing all inline

### Key Insight

**Don't lose your RAG's advantage** (citations, images, sources) but **adopt Gemini's formatting excellence** (structure, emphasis, tables). The goal is: **Gemini's format + Your RAG's citations = Best of both worlds!**
