# Implementation Plan: Options A, B, and D

This plan details the implementation of three enhancements to the PQCSecure Data Transmission System:
1. **Option A (Steganalysis)**: Live Chi-Square steganalysis detector in the UI metrics panel to show LSB detection probability/risk.
2. **Option B (Lossless Format Alerts)**: Warning banners in image uploaders when lossy JPEG images are uploaded.
3. **Option D (Architecture Tab)**: Interactive, high-tech SVG block diagram showing the system data flow under a new navigation tab.

---

## User Review Required

> [!IMPORTANT]
> The backend steganalysis uses a Wilson-Hilferty Chi-Square distribution CDF approximation to compute LSB stego presence probability (0.0 to 1.0). This was implemented inside `steganography.py` as `calculate_chi_square_detector`. We will now call it in `app.py` `/api/encrypt-embed` to retrieve probabilities for both the cover image and the generated stego image and return them to the client.

---

## Proposed Changes

### Backend Changes

#### [MODIFY] [app.py](file:///c:/Users/anilk/Downloads/pqc-1/pqcsecure-backend/app.py)
- In `/api/encrypt-embed` endpoint:
  - Calculate `cover_chi_prob` using `steganography.calculate_chi_square_detector(cover_img)`.
  - Calculate `stego_chi_prob` using `steganography.calculate_chi_square_detector(stego_img)`.
  - Return `cover_chi_prob` and `stego_chi_prob` in the JSON response (rounded to 4 decimal places).

---

### Frontend Changes

#### [MODIFY] [App.jsx](file:///c:/Users/anilk/Downloads/pqc-1/pqcsecure-frontend/src/App.jsx)

- **Option A (Steganalysis UI Display)**:
  - **In Playground (Step 2 - Results)**:
    - Display a **Steganalysis Risk Analysis** card under the visualization.
    - Show cover image stego probability vs. stego image stego probability side-by-side.
    - Include colored risk level badges:
      - **Low Risk (Green)**: Probability < 30%
      - **Med Risk (Yellow)**: Probability 30% - 70%
      - **High Risk (Red)**: Probability > 70%
  - **In Manual Encrypt Result**:
    - Display Cover and Stego steganalysis probabilities with risk badges.

- **Option B (Lossless Format Alerts)**:
  - Add a helper function/validation `isLossyImage(file)` checking if the file is of type `"image/jpeg"` or has extensions `.jpg` or `.jpeg`.
  - Display warning banners styled in cyberpunk warning colors (orange/amber borders and text, dark translucent backgrounds):
    1. **Playground Step 1 (Custom Upload)**: Display the warning below the custom upload box if a JPEG is uploaded.
    2. **Manual Encrypt**: Display the warning below the cover image upload dropzone if a JPEG is uploaded.
    3. **Manual Decrypt**: Display the warning below the stego image upload dropzone if a JPEG is uploaded.

- **Option D (Architecture Tab)**:
  - Add `"architecture"` to the tab selection menu: `🧪 STEP-BY-STEP PLAYGROUND`, `🔒 ENCRYPT & HIDE`, `🔓 EXTRACT & DECRYPT`, `📐 SYSTEM ARCHITECTURE`, `📊 BENCHMARKS`.
  - Create a new component `ArchitectureDiagram` containing:
    - An interactive, detailed SVG block diagram representing the full pipeline (Sender Alice, Channel, Receiver Bob).
    - Glowing animated lines indicating the direction of data flow.
    - Interactive elements: hovering or clicking on a block (e.g., KEM KeyGen, KEM Encaps, AES Encrypt, LSB Embed, Channel, LSB Extract, KEM Decaps, AES Decrypt) shows a detailed cyberpunk information card explaining what happens in that phase (algorithms, security properties, etc.).

---

## Verification Plan

### Automated Tests
- Run `npm run build` in the frontend directory to ensure there are no build errors.

### Manual Verification
- **Lossy Format warning**: Upload a JPEG in all three places and verify that the orange warning banner displays correctly. Upload a PNG and verify that no warning displays.
- **Steganalysis detector**: Perform encryption in the playground and manual tabs, verify that cover probability is close to 0% (Low Risk) and stego probability is visible (High Risk if payload is large relative to image size, or Low Risk if it's very small).
- **Architecture diagram**: Navigate to the "System Architecture" tab, verify the SVG renders beautifully, hovered nodes glow and show details, and clicked nodes lock details.
