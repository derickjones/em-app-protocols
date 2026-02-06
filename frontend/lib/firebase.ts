/**
 * Firebase Configuration
 * Initializes Firebase Auth for the EM Protocol app
 */

import { initializeApp, getApps } from "firebase/app";
import { getAuth, GoogleAuthProvider, OAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyB5zFvhhcLVAJ4aYgJT3MlhhUY__k8egMk",
  authDomain: "clinical-assistant-457902.firebaseapp.com",
  projectId: "clinical-assistant-457902",
  storageBucket: "clinical-assistant-457902.firebasestorage.app",
  messagingSenderId: "930035889332",
  appId: "1:930035889332:web:4bb03b87246f2d65d813e1",
};

// Initialize Firebase only if not already initialized
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
export const microsoftProvider = new OAuthProvider('microsoft.com');

// Configure Microsoft provider for multi-tenant (any org + personal accounts)
microsoftProvider.setCustomParameters({
  tenant: 'common',
  prompt: 'select_account'
});
