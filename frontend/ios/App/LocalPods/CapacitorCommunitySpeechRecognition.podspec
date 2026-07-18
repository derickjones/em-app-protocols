Pod::Spec.new do |s|
  s.name = 'CapacitorCommunitySpeechRecognition'
  s.version = '7.0.1'
  s.summary = 'A native plugin for speech recognition'
  s.license = 'MIT'
  s.homepage = 'https://github.com/capacitor-community/speech-recognition'
  s.author = 'Ionic Team'
  # Required attribute, but ignored — this podspec is only ever consumed via
  # the Podfile's `:path =>` (a local/development pod), never fetched by URL.
  s.source = { :git => '' }
  # Locally patched: upstream podspec (node_modules/@capacitor-community/speech-recognition)
  # declares `s.dependency 'Capacitor'`, which pulls in a second copy of the
  # Capacitor runtime alongside the SPM-linked one in CapApp-SPM/Package.swift,
  # causing duplicate module/symbol conflicts. Dropped here — the plugin's
  # `import Capacitor` resolves fine against the SPM-provided product once both
  # are embedded in the same App target.
  s.source_files = '../../../node_modules/@capacitor-community/speech-recognition/ios/Plugin/**/*.{swift,h,m,c,cc,mm,cpp}'
  s.ios.deployment_target = '14.0'
  s.swift_version = '5.1'
end
