# Articulate
Attempt to build a personal speaking trainer

  ---
  PC profile: heavier models

  .env.pc automatically uses:
  - WHISPER_MODEL=large-v3 (vs base on laptop)
  - OLLAMA_MODEL=gemma3:12b (vs gemma3:1b)
  - WHISPER_DEVICE=cuda (GPU, not CPU)

  Just run .\run.ps1 pc — the config is already wired.

  ---
  Using a microphone directly on the PC (simplest setup)

  Browsers grant microphone access to localhost without HTTPS. No certs needed.

  1. Start the backend:
     .\run.ps1 pc

  2. In a separate terminal, start the frontend:
     cd frontend && bun run dev

  3. Open http://localhost:5173 in your browser. The mic will work.

  That's it. Certs are only needed when using your phone as a remote microphone over WiFi.

  ---
  Phone as microphone (phone → PC server over WiFi)

  Browsers block the mic on non-HTTPS, non-localhost origins. Your phone on WiFi is neither, so you need HTTPS with a trusted cert. The code already supports this — you just need the certs once.

  One-time setup (on PC)

  # Install mkcert (if not already)
  winget install FiloSottile.mkcert

  # Install the root CA into Windows trust store
  mkcert -install

  # Generate cert for your PC's LAN IP (check with ipconfig)
  # Run from the Articulate repo root
  mkdir certs
  cd certs
  mkcert 192.168.x.x localhost 127.0.0.1
  # Renames output to cert.pem / key.pem:
  Rename-Item "192.168.x.x+2.pem" cert.pem
  Rename-Item "192.168.x.x+2-key.pem" key.pem
  cd ..

  Install CA on phone

  - Find %LOCALAPPDATA%\mkcert\rootCA.pem on the PC
  - Transfer it to the phone (AirDrop / email / USB)
  - Android: Settings → Security → Install certificate → CA certificate
  - iPhone: Settings → General → VPN & Device Management → install profile, then Settings → General → About → Certificate Trust Settings → enable

  Start the server

  # Build the frontend first (backend serves it at :8000)
  cd frontend && bun run build && cd ..
  .\run.ps1 pc

  run.ps1 detects certs/cert.pem and automatically adds --ssl-certfile + --ssl-keyfile.

  Access from phone

  Open https://192.168.x.x:8000 on your phone (replace with your PC's LAN IP from ipconfig). The browser will ask for mic permission and it will work.

  ▎ Alternative: skip the build step and run the Vite dev server instead (cd frontend && bun run dev).
  ▎ Then open https://192.168.x.x:5173 on your phone instead.