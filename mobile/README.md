# Tog & Dogs Mobile Operations Portal

This directory houses the React Native / Expo native mobile application for the Tog & Dogs operations manager and staff. The application is built on top of Expo, React Navigation, and secure Amazon Cognito federated credentials, integrating seamlessly with the production API.

---

## 🚀 Getting Started

### 1. Prerequisites

Make sure you have the following installed on your machine:
* **Node.js** (v18 or v20 recommended)
* **npm** (comes with Node)
* **Expo Go** application on your physical device (search for "Expo Go" in the Apple App Store or Google Play Store)

### 2. Local Installation

Navigate to the mobile directory and install local dependencies:

```bash
cd mobile
npm install
```

### 3. Run Dev Server

Start the local Metro Bundler:

```bash
npm run start
```

This starts the Expo local server (typically on port `8081`) and prints a large QR code in your terminal.

---

## 📱 Launching on Devices

### A. Physical Phone/Tablet (Recommended)
1. Ensure your computer and your phone are connected to the **same local Wi-Fi network**.
2. **iOS:** Open your system Camera app and scan the QR code printed in the terminal, then tap the "Open in Expo" prompt.
3. **Android:** Open the **Expo Go** app and tap "Scan QR Code" at the top, then scan the terminal code.

### B. Emulator / Simulator
* Press `i` in the terminal to launch on the iOS Simulator (requires Xcode on macOS).
* Press `a` in the terminal to launch on the Android Virtual Device (AVD) (requires Android Studio).
* Press `w` in the terminal to run in a web browser wrapper.

---

## 🔐 Auth & Role-Based Navigation

The application interfaces directly with the live AWS Cognito User Pools and decodes JWT identity tokens on load to structure navigation dynamically:

1. **Owner / Admin (e.g., Ryan):** Logs in and gains access to the **Admin Dashboard** and **Intake Requests Queue** tabs.
2. **Staff:** Logs in and gains access to the **My Daily Schedule** visit calendar tab.
3. **Clients:** Logs in and gains access to the **My Pet Bookings** appointment tracking tab.
