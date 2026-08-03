# PQCSecure — Full Project Report

## 1. Project Title
PQCSecure — Post-Quantum Secure Data Transmission System

## 2. Project Overview
PQCSecure is a security-focused prototype system that combines modern post-quantum cryptography, adaptive image steganography, and real-time steganalysis. The project is designed to demonstrate how encrypted payloads can be hidden inside carrier images so that the transmission remains both confidential and less detectable to metadata-aware observers.

The solution is developed as a layered defense system:
- Post-quantum key encapsulation for secure key exchange
- Symmetric encryption for data confidentiality
- Image steganography for covert transport
- Steganalysis tools for risk awareness and detection feedback

## 3. Problem Statement
Traditional public-key cryptography is vulnerable to quantum attacks. Algorithms such as RSA and ECC are no longer considered safe against the future capability of large-scale quantum computers. This creates a pressing need to transition to post-quantum cryptographic algorithms.

At the same time, post-quantum algorithms often introduce larger key sizes and ciphertext sizes. These larger payloads can raise suspicion when transmitted directly over networks. This is where steganography becomes valuable: the payload is hidden inside a visually normal image so that the transmission does not stand out as an obvious cryptographic exchange.

## 4. Main Objectives
The project aims to achieve the following goals:

1. Implement a quantum-safe key exchange workflow using ML-KEM-768.
2. Encrypt messages using authenticated symmetric encryption.
3. Hide encrypted payloads inside images using adaptive steganography.
4. Preserve image quality and reduce visual distortion.
5. Provide steganalysis warning tools before transmission.
6. Benchmark the design for feasibility on Raspberry Pi-class edge hardware.

## 5. System Architecture
The system consists of three major parts:

### 5.1 Backend
The backend is implemented in Python with Flask.
It handles:
- key generation
- encryption and decryption
- payload packaging and parsing
- adaptive LSB steganography embedding/extraction
- statistical analysis and AI-based stego detection
- benchmarking utilities

### 5.2 Frontend
The frontend is built with Vite + React.
It provides:
- an interactive UI
- dashboards for steganalysis features
- architecture visualization
- user-friendly experimentation""" tools

### 5.3 Benchmarking Suite
The benchmark suite is focused on performance evaluation and hardware viability, especially on edge devices such as Raspberry Pi 4.

## 6. Core Workflow
The sender-receiver operation works as follows:

1. The receiver generates a keypair using ML-KEM-768.
2. The public key is shared with the sender.
3. The sender encapsulates a shared secret and encrypts the message.
4. The encrypted data is compiled into a binary payload.
5. The payload is embedded into the least significant bits of a cover image.
6. The resulting stego image is sent to the receiver.
7. The receiver extracts the payload from the image.
8. The receiver decapsulates the shared secret.
9. The ciphertext is decrypted and verified.
10. The original plaintext is recovered.

## 7. Cryptographic Features
PQCSecure supports multiple cryptographic schemes for comparison and experimentation.

### 7.1 Post-Quantum KEM
- ML-KEM-768
  - Standardized post-quantum algorithm
  - Lattice-based security
  - Category 3 security level
  - Large public key and ciphertext sizes

### 7.2 Classical Baselines
- X25519
- RSA-2048

These classical options are included to compare performance and overhead against post-quantum security.

### 7.3 Symmetric Encryption
- AES-256-GCM (recommended)
- AES-256-CBC (legacy comparison mode)

AES-256-GCM is preferred because it provides confidentiality and integrity together.

## 8. Steganography Layer
The hiding layer is one of the project’s most important components.

### 8.1 Adaptive LSB Embedding
The payload is embedded into the least significant bits of pixels. However, the implementation is not naïve linear embedding across the full image.

Instead, it prefers:
- high-texture regions
- noisy or edge-rich blocks
- areas where embedding is harder to detect visually or statistically

### 8.2 Texture Analysis
The system evaluates local image texture using block-based analysis, typically using 32×32 blocks. It computes image complexity and prioritizes regions with stronger signal variation.

This approach improves the stealth of the message by placing data in areas where LSB changes are naturally less noticeable.

### 8.3 Bit Depth Support
The system supports configurable bit depths:
- 1 BPP
- 2 BPP
- 3 BPP

This allows trade-offs between payload capacity and visual stealth.

## 9. Steganalysis Support
To make the system safer and more practical, PQCSecure includes detection tools that estimate whether a cover image has been altered in a suspicious way.

### 9.1 Statistical Chi-Square Detector
This detector measures statistical imbalance in LSB distributions. When data is embedded, the histogram of pixel pairs tends to become less natural than in a clean image.

### 9.2 AI-Based Random Forest Detector
The model uses image-derived features to classify whether a cover image is likely to contain hidden data. The feature set includes:
- unique color ratio
- Chi-square probability
- entropy of LSB planes
- horizontal difference statistics
- parity asymmetry
- Laplacian variance

This gives the system a dual-defense mechanism: one statistical and one machine-learning-driven.

## 10. Features Summary
The main features of the project are:

### Security Features
- Quantum-safe key exchange with ML-KEM-768
- AES-256-GCM authenticated encryption
- Secure payload packing and parsing
- Receiver-side decryption workflow

### Steganography Features
- Adaptive LSB hiding
- Texture-aware embedding
- Bit-depth configuration
- Lossless image suitability guidance

### Analysis Features
- Chi-square steganalysis
- Random Forest stego detection
- Image quality and risk feedback

### Benchmarking Features
- Algorithm comparison
- KEM latency evaluation
- Encryption/decryption throughput measurement
- Edge-device compatibility testing

## 11. Performance Observations
The benchmark results show that ML-KEM-768 is significantly faster than RSA for key generation and is practical for edge environments. Its large payload sizes, however, make direct transmission suspicious or inefficient. This reinforces the need for adaptive steganographic transport.

The project’s benchmark results also show that the Raspberry Pi 4 remains feasible for this prototype use case, especially for key encapsulation and moderate stego processing tasks.

## 12. Strengths of the Project
- Strong research-style integration of cryptography and steganography
- Post-quantum security focus
- Useful dual-detection architecture for stego risk evaluation
- Good educational value for secure communication systems
- Portable and benchmarkable for edge environments

## 13. Limitations
- This is a prototype, not a production-grade hardened cryptographic deployment
- Steganography effectiveness depends on the quality and characteristics of the carrier image
- JPEG images are not suitable for reliable LSB transport because of lossy compression
- Real-world deployment would require stronger operational controls and validation

## 14. Use Cases
This project is suitable for:
- secure research demonstrations
- IoT and edge-device communication prototypes
- privacy-preserving data transport experiments
- postgraduate or academic project work on post-quantum security

## 15. Conclusion
PQCSecure demonstrates a practical and conceptually strong approach to secure data transmission in the post-quantum era. It combines quantum-safe cryptography, covert transport, and active detection tools in one integrated workflow.

The project highlights an important reality: future secure communication systems will not rely on cryptography alone. They will also need to account for transmission patterns, metadata leakage, and covert-channel resilience.

## 16. Final Summary
PQCSecure is a hybrid post-quantum secure communication platform that merges:
- ML-KEM-768 for quantum-safe key exchange
- AES-256-GCM for authenticated encryption
- Adaptive LSB steganography for covert payload transport
- Statistical and AI-based steganalysis for operational awareness

This makes the project a strong prototype for secure, stealth-oriented communication in modern and future threat environments.
