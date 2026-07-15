import type { CapacitorConfig } from '@capacitor/cli';
import { KeyboardResize } from '@capacitor/keyboard';

const config: CapacitorConfig = {
  appId: 'app.emergencymedicine.ios',
  appName: 'EMA',
  webDir: 'out',
  plugins: {
    FirebaseAuthentication: {
      skipNativeAuth: false,
      providers: ['google.com'],
    },
    Keyboard: {
      resize: KeyboardResize.Native,
      autoBackdropColor: 'auto',
    },
  },
  experimental: {
    ios: {
      spm: {
        packageOptions: {
          '@capacitor-firebase/authentication': {
            symlink: true,
          },
        },
      },
    },
  },
};

export default config;
